from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re

import sys; sys.path.insert(0, 'ColBERT/')
import colbert
from colbert import Indexer, Searcher
from colbert.infra import Run, RunConfig, ColBERTConfig
from colbert.data import Queries, Collection
import datetime
import threading
import faiss
import time
from pathlib import Path

root_path = 'dsp'
import cohere
from datasets import load_dataset
import openai
import os
import dsp

os.environ["DSP_NOTEBOOK_CACHEDIR"] = os.path.join(root_path, 'cache')
openai_key = ''
cohere_key = ''
colbert_server = 'http://index.contextual.ai:8893/api/search'
#lm = dsp.Cohere(model='command-xlarge-nightly', api_key=cohere_key)
lm = dsp.GPT3(model='text-davinci-001', api_key=openai_key)
rm = dsp.ColBERTv2(url=colbert_server)
dsp.settings.configure(lm=lm, rm=rm)

squad = load_dataset("squad")
def get_squad_split(squad, split="validation"):
    """
    Use `split='train'` for the train split.

    Returns
    -------
    list of SquadExample named tuples with attributes
    id, title, context, question, answers

    """
    data = zip(*[squad[split][field] for field in squad[split].features])
    return [dsp.Example(id=eid, title=title, context=context, question=q, answer=a['text'])
            for eid, title, context, q, a in data]
squad_train = get_squad_split(squad, split="train")

Question = dsp.Type(
    prefix="Question:",
    desc="${the question to be answered}")

Answer = dsp.Type(
    prefix="Answer:",
    desc="${a short factoid answer, often between 1 and 5 words}",
    format=dsp.format_answers)

Context = dsp.Type(
    prefix="Context:\n",
    desc="${sources that may contain relevant content}",
    format=dsp.passages2text)

qa_template_with_passages = dsp.Template(
    instructions="Answer questions with short factoid answers.",
    context=Context(),
    question=Question(),
    answer=Answer())
    
@dsp.transformation
def filter_demos(d):
    print("Filtering valid passages for demonstrations questions.")
    passages = list(filter(lambda p: dsp.passage_match(d.answer, p) is True, dsp.retrieve(d.question, k=3)))
    if len(passages) == 0:
        return None
    d.context = passages[0]
    d.demos = dsp.sample(squad_train, k=3)

    generator = dsp.generate(qa_template_with_passages)
    d, completions = generator(d, stage='qa')
    
    if dsp.answer_match(completions.answer, d.answer) is False:
        return None
    return d

@dsp.transformation
def openqa(example, train=squad_train, k=1):
#    with dsp.settings.context(vectorizer=dsp.SentenceTransformersVectorizer()):
#        print("Running knn to do clustering on questions...")
#        knn_func = dsp.knn(squad_train)
#    knn_res_train_vec = knn_func(example, 10) # select 10 questions most closed to the example
#    demo_samples = knn_res_train_vec

    demo_samples = dsp.sample(train, k=10)
    annotated_demos = dsp.annotate(filter_demos)(demo_samples, k=k)
    example.demos = annotated_demos
    generator = dsp.generate(qa_template_with_passages, n=20, temperature=0.7) # temperature=0.7
    example, completions = generator(example, stage='qa')
    completions = dsp.majority(completions) # use majority

    return completions



def search(collection, query, index_name):
    with Run().context(RunConfig(experiment='notebook')):
        searcher = Searcher(index=index_name, collection=collection)
    passages = searcher.search(query, k=1) # select only 5 relevant passage since the context is not very large
    for passage_id, passage_rank, passage_score in zip(*passages):
        id = passage_id
        print(f"\t [{passage_rank}] \t\t {passage_score:.1f} \t\t {searcher.collection[passage_id]}")
    return searcher.collection[passage_id]

def index(collection, title):
    nbits = 2   # encode each dimension with 2 bits
    doc_maxlen = 300 # truncate passages at 300 tokens
    checkpoint = 'colbert-ir/colbertv2.0'
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    index_name = f'page.content_{title}'
    
    index_path = Path(f'experiments/notebook/indexes/{index_name}')
    if not index_path.exists():
        with Run().context(RunConfig(nranks=1, experiment='notebook')):  # nranks specifies the number of GPUs to use
            config = ColBERTConfig(doc_maxlen=doc_maxlen, nbits=nbits, kmeans_niters=4) # kmeans_niters specifies the number of iterations of k-means clustering; 4 is a good and fast default.
                                                                                        # Consider larger numbers for small datasets.
            indexer = Indexer(checkpoint=checkpoint, config=config)
            indexer.index(name=index_name, collection=collection, overwrite=True)
    return index_name
        
        
#    query = "When was Apple founded?"
#    passages_results = searcher.search(query, k=3)
#    for passage_id, passage_rank, passage_score in zip(*passages_results):
#        print(f"\t [{passage_rank}] \t\t {passage_score:.1f} \t\t {searcher.collection[passage_id]}")

class RequestHandler(BaseHTTPRequestHandler):
    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()

    def do_POST(self):
        searcher = None
        searcher_initialized_event = threading.Event()
        # Check if the path is what we expect
        if self.path == '/question':
            # Collect the length of the POST payload
            content_length = int(self.headers['Content-Length'])
            # Read the data
            post_data = self.rfile.read(content_length)
            # Convert bytes to string type and string type to dict
            post_data = json.loads(post_data.decode('utf-8'))
            
            # Here, you can process the post_data to generate your response
            # For now, we'll just send back a sample response
            user_message = post_data['userMessage']
            page_content = post_data['pageContent']
            page_title = post_data['pageTitle']
            for i, paragraph in enumerate(page_content):
                page_content[i] = re.sub(r'\[\d+\]', '', paragraph)

            index_name = index(page_content, page_title)
            passages = search(page_content, user_message, index_name)
            answer = openqa(dsp.Example(question=user_message, context=passages)).answer
            response = {
                'response': f"{answer} \n"
            }
            # Respond with a JSON string
            self._set_headers()
            self.wfile.write(json.dumps(response).encode('utf-8'))
        else:
            self.send_error(404, "File Not Found: %s" % self.path)

def run(server_class=HTTPServer, handler_class=RequestHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting http server on port {port}...')
    httpd.serve_forever()

# Run the server
if __name__ == '__main__':
    run()
