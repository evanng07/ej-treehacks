# app.py
from flask import Flask, jsonify, render_template, request, current_app
import os
import ast
import json
import builtins



app = Flask(__name__, template_folder='templates')
call_graph_data = {}  # Global variable to store analysis results

def update_call_graph_data(data):
    """Update the global call graph data."""
    global call_graph_data
    call_graph_data.clear()
    call_graph_data.update(data)

# --- Analyzer Functions ---
class CallGraphAnalyzer(ast.NodeVisitor):
    def __init__(self, source):
        self.call_graph = {}
        self.function_code = {}
        self.source = source
        self.current_function = None

    def visit_FunctionDef(self, node):
        prev_function = self.current_function
        self.current_function = node.name
        if node.name not in self.call_graph:
            self.call_graph[node.name] = []
        code_snippet = ast.get_source_segment(self.source, node)
        self.function_code[node.name] = code_snippet if code_snippet else ""
        self.generic_visit(node)
        self.current_function = prev_function

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr
        else:
            func_name = "unknown"
        if self.current_function:
            self.call_graph[self.current_function].append(func_name)
        self.generic_visit(node)

def analyze_file(filepath):
    with open(filepath, "r", encoding="utf-8") as file:
        source = file.read()
    tree = ast.parse(source, filename=filepath)
    analyzer = CallGraphAnalyzer(source)
    analyzer.visit(tree)
    result = {}
    for func in analyzer.call_graph:
        result[func] = {
            "code": analyzer.function_code.get(func, ""),
            "calls": analyzer.call_graph[func]
            # "file" and "breadcrumbs" will be added in analyze_directory.
        }
    return result

def analyze_directory(directory):
    """
    Analyze all Python files in the given directory.
    For each function, add:
      - "file": the relative file path where the function is defined.
      - "breadcrumbs": a string showing the file's directory hierarchy.
    Then, filter out calls to functions that are built-ins or not defined in the codebase.
    """
    complete_graph = {}
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                relative_path = os.path.relpath(filepath, directory)
                file_graph = analyze_file(filepath)
                for func in file_graph:
                    file_graph[func]["file"] = relative_path
                    breadcrumbs = " > ".join(relative_path.split(os.sep))
                    file_graph[func]["breadcrumbs"] = breadcrumbs
                complete_graph.update(file_graph)
    
    defined_functions = set(complete_graph.keys())
    built_in_names = {name for name, obj in vars(builtins).items() if callable(obj)}
    
    for func, details in complete_graph.items():
        details["calls"] = [
            call for call in details["calls"]
            if call in defined_functions and call not in built_in_names
        ]
    return complete_graph

# --- Flask Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/data")
def data():
    return jsonify(call_graph_data)

@app.route('/chatbot', methods=['POST'])
def chatbot_query():
    data = request.get_json()
    user_query = data.get('query')
    if not user_query:
        return jsonify({'response': 'No query provided.'}), 400

    # Send the query to Groq's Mixtral model via the Groq client.
    response_text = call_groq_chat(user_query)
    return jsonify({'response': response_text})

def call_groq_chat(query):
    """
    Use Groq's Python client to send a chat request to Mixtral.
    The messages list includes the user query.
    """
    try:
        client = current_app.config['GROQ_CLIENT']  # Access the client from the app's config
        # Here we pass the user query as a message.
        completion = client.chat.completions.create(
            model="mixtral-8x7b-32768",
            messages=[{"role": "user", "content": query}],
            temperature=1,
            max_completion_tokens=1024,
            top_p=1,
            stream=False,  # For simplicity, we disable streaming here.
            stop=None,
        )
        answer = completion.choices[0].message.content
        return answer
    except Exception as e:
        return f"Error calling Groq API: {str(e)}"

if __name__ == "__main__":
    # Optionally, update call_graph_data here by analyzing a directory:
    # call_graph_data = analyze_directory("your_code_directory")
    app.run(debug=True)