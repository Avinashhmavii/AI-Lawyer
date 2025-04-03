from flask import Flask, request, render_template, jsonify
from groq import Groq
from pypdf import PdfReader
import io
import re

app = Flask(__name__)

# Set Groq API key
GROQ_API_KEY = "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"

# Initialize Groq client
client = Groq(api_key=GROQ_API_KEY)

def extract_text_from_pdf(uploaded_file):
    """Extract text content from PDF file using pypdf"""
    try:
        reader = PdfReader(io.BytesIO(uploaded_file.read()))
        text = ""
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:  # Handle None values
                text += extracted
        return text[:4000]  # Return first 4000 characters for demo
    except Exception as e:
        return f"Error processing PDF: {str(e)}"

def generate_response(prompt, context, agent_role):
    """Generate response using Groq's API with role-specific prompting"""
    system_prompt = f"""
    You are a legal {agent_role} AI assistant. Analyze the provided legal document and:
    {{
        "Legal Researcher": "Find relevant precedents, cite legal statutes, and provide authoritative references. Provide detailed research summaries with sources and references specific sections from uploaded documents.",
        "Contract Analyst": "Identify key clauses, highlight risks, and suggest contractual improvements. Specializes in thorough contract review, identifying key terms, obligations, and potential issues. References specific clauses from documents for detailed analysis.",
        "Legal Strategist": "Develop litigation strategies, assess outcomes, and recommend action plans. Focuses on developing comprehensive legal strategies, providing actionable recommendations while considering both risks and opportunities.",
        "Team Lead": "Coordinates analysis between team members, ensures comprehensive responses, properly sourced recommendations, and references to specific document parts. Acts as an Agent Team coordinator for all three agents."
    }}[agent_role]
    """
    
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Document context: {context}\n\nQuestion: {prompt}"}
            ],
            temperature=0.3,
            max_tokens=1024
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error in {agent_role} analysis: {str(e)}"

def format_response(response):
    """Format the raw response into neat HTML"""
    # Split response by agent sections
    sections = re.split(r'\*\*(.*?):\*\*', response)
    formatted = ""
    
    for i in range(1, len(sections), 2):  # Start at 1 to get agent name first
        agent = sections[i].strip()
        content = sections[i + 1].strip()
        
        # Split content into paragraphs or list items
        lines = content.split('\n')
        formatted_content = ""
        in_list = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            # Check if line starts with a number (e.g., "1. ") to treat as list item
            if re.match(r'^\d+\.\s', line):
                if not in_list:
                    formatted_content += "<ul>"
                    in_list = True
                formatted_content += f"<li>{line}</li>"
            else:
                if in_list:
                    formatted_content += "</ul>"
                    in_list = False
                formatted_content += f"<p>{line}</p>"
        
        if in_list:
            formatted_content += "</ul>"
        
        formatted += f"<div class='agent-section'><h3>{agent}</h3>{formatted_content}</div>"
    
    return formatted if formatted else f"<p>{response}</p>"  # Fallback for unformatted text

# Store chat history in memory (for simplicity; use a database for production)
chat_history = []
context = ""

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", chat_history=chat_history)

@app.route("/upload", methods=["POST"])
def upload_file():
    global context
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if file and file.filename.endswith(".pdf"):
        context = extract_text_from_pdf(file)
        if context and "Error" not in context:
            return jsonify({"message": "Document ready for analysis!"}), 200
        else:
            return jsonify({"error": context or "Failed to process document"}), 400
    return jsonify({"error": "Invalid file type. Please upload a PDF."}), 400

@app.route("/chat", methods=["POST"])
def chat():
    global context
    data = request.get_json()
    prompt = data.get("prompt")
    analysis_type = data.get("analysis_type")

    if not prompt or not analysis_type:
        return jsonify({"error": "Missing prompt or analysis type"}), 400
    if not context:
        return jsonify({"error": "Please upload a document first!"}), 400

    # Map analysis types to active agents
    analysis_agents = {
        "Contract Review": ["Contract Analyst"],
        "Legal Research": ["Legal Researcher"],
        "Risk Assessment": ["Legal Strategist", "Contract Analyst"],
        "Compliance Check": ["Legal Strategist", "Legal Researcher", "Contract Analyst"],
        "Custom Queries": ["Legal Researcher", "Legal Strategist", "Contract Analyst", "Team Lead"]
    }

    # Generate responses from active agents
    active_agents = analysis_agents[analysis_type]
    response = ""
    for agent in active_agents:
        agent_response = generate_response(prompt, context, agent)
        response += f"**{agent}:**\n{agent_response}\n\n"

    # Format the response for neat display
    formatted_response = format_response(response)

    # Update chat history
    chat_history.append({"role": "user", "content": prompt})
    chat_history.append({"role": "assistant", "content": formatted_response})

    return jsonify({"response": formatted_response}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
