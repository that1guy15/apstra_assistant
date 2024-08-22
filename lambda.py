import json
import os
from typing import List, Dict
from pprint import pprint as pp

from dotenv import load_dotenv

from mangum import Mangum
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
from langchain.chains import APIChain
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import PromptTemplate
from langchain_openai import OpenAI, ChatOpenAI
from pydantic import BaseModel

load_dotenv()
open_api_key = os.environ.get("OPEN_API_KEY")
github_api_key = os.environ.get("GITHUB_API_KEY")
langchain_api_key = os.environ.get("LANGCHAIN_API_KEY")
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "Apstra-Assistant"
os.environ["LANGCHAIN_WANDB_TRACING"] = "false"



app = FastAPI()
handler = Mangum(app)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Paths to include in the API docs
filter_paths = [
    '/api/aaa/login',
    '/api/blueprints',
    '/api/blueprints/{blueprint_id}',
    '/api/blueprints/{blueprint_id}/qe',
    '/api/blueprints/{blueprint_id}/systems',
    '/api/blueprints/{blueprint_id}/anomalies-history',
    '/api/blueprints/{blueprint_id}/anomalies'
]

def filter_openapi_spec(included_paths: List, api_spec: Dict) -> Dict:
    """
    Filters the OpenAI API spec to include only the specified paths and their relevant definitions.

    Args:
    strings (list of str): List of strings to match against the API spec paths.
    api_spec (dict): The OpenAI API spec dictionary.

    Returns:
    dict: A new API spec dictionary with only the specified paths and relevant definitions.
    """
    # Initialize the new filtered API spec
    filtered_spec = {
        "swagger": api_spec.get("swagger", "2.0"),
        "servers": api_spec.get("servers", []),
        "basePath": api_spec.get("basePath", "/"),
        "schemes": api_spec.get("schema", "https"),
        "consumes": api_spec.get("consumes", ["application/json"]),
        "produces": api_spec.get("produces", ["application/json"]),
        "securityDefinitions": api_spec.get("securityDefinitions", {'APIKeyHeader': {'in': 'header', 'name': 'AUTHTOKEN', 'type': 'apiKey'}}),
        "security": api_spec.get("security", [{'APIKeyHeader': []}]),
        "paths": {},
        "definitions": {},  # For OpenAPI 2.0
        "info": api_spec.get("info", {'description': 'AOS REST API', 'title': 'AOS', 'version': '5.0.0'}),
    }

    # Filter the paths
    for path in included_paths:
        if path in api_spec["paths"]:
            filtered_spec["paths"][path] = api_spec["paths"][path]

    # Gather all definitions referenced in the filtered paths
    referenced_definitions = set()
    for path in filtered_spec["paths"].values():
        for method in path.values():
            if 'parameters' in method:
                for param in method['parameters']:
                    if '$ref' in param:
                        ref = param['$ref'].split('/')[-1]
                        referenced_definitions.add(ref)
            if 'responses' in method:
                for response in method['responses'].values():
                    if 'schema' in response and '$ref' in response['schema']:
                        ref = response['schema']['$ref'].split('/')[-1]
                        referenced_definitions.add(ref)

    # Include the relevant definitions in the filtered spec
    for ref in referenced_definitions:
        if ref in api_spec.get("definitions", {}):
            filtered_spec["definitions"][ref] = api_spec["definitions"][ref]
        # Uncomment for OpenAPI 3.0
        # if ref in api_spec.get("components", {}).get("schemas", {}):
        #     filtered_spec["components"]["schemas"][ref] = api_spec["components"]["schemas"][ref]

    return filtered_spec


# Load Apstra Server API docs
def build_apstra_docs(apstra_server: str, include_paths: list[str]) -> dict:
    docs_raw = requests.get(f"{apstra_server}api/docs")
    if docs_raw.status_code == 200:
        apstra_api_docs = docs_raw.json()
        apstra_api_docs["host"] = apstra_server
        apstra_api_docs["servers"] = [
                    {
                        "url": apstra_server,
                        "description": "Apstra Server"
                    }
                ],
    else:
        raise Exception(f"Failed to get Apstra API Docs. Error: {docs_raw.text}")

    return filter_openapi_spec(include_paths, apstra_api_docs)


# Apstra Tools
def apstra_login(apstra_server: str, username: str, password: str) -> dict:
    payload = {
        "username": username,
        "password": password
    }
    headers = {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'AuthToken': ""
    }

    try:
        resp = requests.post(url=f"{apstra_server}/api/aaa/login", json=payload)
        if resp.status_code == 201:
            headers["AuthToken"] = resp.json().get("token")
            print(f"Successfully authenticated with {apstra_server}")
            return headers
        else:
            print(f"Failed to authenticate. Status code: {resp.status_code}")
            return None
    except Exception as e:
        print(f"Failed to authenticate. Error: {e}")
        return None


def ensure_trailing_slash(url: str) -> str:
    if not url.endswith('/'):
        url += '/'
    return url

# Set Prompts
api_url_template = """
Given the following API Documentation for the Apstra API: {api_docs} 
Your task is to construct the most efficient API URL to answer the user's question, ensuring the 
call is optimized to include only necessary information.
Question: {question}
API URL:
"""
api_url_prompt = PromptTemplate(input_variables=['api_docs', 'question'],
                                template=api_url_template)

api_response_template = """"
With the API Documentation for the Apstra API: {api_docs} 
and the specific user question: {question} in mind,
and given this API URL: {api_url} for querying, here is the 
response from the Apstra API: {api_response}. 
Please provide a summary that directly addresses the user's question, 
omitting technical details like response format, and 
focusing on delivering the answer with clarity and conciseness, 
as if Apstra itself is providing this information.
Summary:
"""
api_response_prompt = PromptTemplate(input_variables=['api_docs',
                                                      'question',
                                                      'api_url',
                                                      'api_response'],
                                     template=api_response_template)




# Initialize the language model
apstra_api_llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0.0)



# Set shared memory
conversation_memory = ConversationBufferMemory(memory_key="chat_history",
                                               max_len=200,
                                               return_messages=True
                                               )


@app.get("/")
def read_root():
    return {"response": "Hello I am your Apstra Assistant"}


@app.post("/chat")
def chat(request: dict):
    message = request['message'].strip()
    apstra_url = ensure_trailing_slash(request['apstra_url'])
    username = request['username']
    password = request['password']

    # Build Apstra API Docs
    filtered_apstra_spec = build_apstra_docs(apstra_url, filter_paths)

    # Authenticate with Apstra
    auth_headers = apstra_login(apstra_url, username, password)
    if not auth_headers:
        raise Exception("Authentication failed. Cannot proceed without a valid token.")

    # Create the API chain
    api_chain = APIChain.from_llm_and_api_docs(
        llm=apstra_api_llm,
        api_docs=json.dumps(filtered_apstra_spec),
        api_url_prompt=api_url_prompt,
        api_response_prompt=api_response_prompt,
        headers=auth_headers,
        verbose=True,
        limit_to_domains=[apstra_url],
    )

    try:
        resp = api_chain.invoke({"question": message})
        return {"response": resp}
    except Exception as e:
        return {"response": f"Error running chain: {str(e)}"}