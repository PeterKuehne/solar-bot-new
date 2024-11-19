import json
import os
import time
import openai
from openai import OpenAI
from dotenv import load_dotenv
from functions import solar
from functions import calendar_service
from functions.assistant import create_assistants
from flask import Flask, request, jsonify
from config.environment import Environment

# Load environment variables from .env file
load_dotenv()

Environment.init_app()

# Create Flask app
app = Flask(__name__)

# Konfiguration basierend auf Umgebung
if Environment.is_production():
    app.config['SERVER_NAME'] = os.getenv('APP_BASE_URL')
    app.config['PREFERRED_URL_SCHEME'] = 'https'

# Setze JSON-Encoding auf UTF-8
app.config['JSON_AS_ASCII'] = False
app.config['JSONIFY_MIMETYPE'] = "application/json; charset=utf-8"


# Füge UTF-8 Header zu allen Responses hinzu
@app.after_request
def add_utf8_header(response):
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Create or load assistant
solar_assistant_id, calendar_assistant_id = create_assistants(client)


@app.route('/start', methods=['GET'])
def start_conversation():
    print("Starting a new conversation...")
    thread = client.beta.threads.create()
    print(f"New thread created with ID: {thread.id}")
    return jsonify({"thread_id": thread.id})


@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    thread_id = data.get('thread_id')
    user_input = data.get('message', '')
    msg_type = data.get('type', 'solar')

    if not thread_id:
        print("Error: Missing thread_id")
        return jsonify({"error": "Missing thread_id"}), 400

    print(f"Received message: {user_input} for thread ID: {thread_id}")

    try:
        # Add message to thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_input
        )

        # Wähle den richtigen Assistenten
        assistant_id = solar_assistant_id if msg_type == 'solar' else calendar_assistant_id

        if not assistant_id:
            return jsonify({"error": f"No assistant found for type: {msg_type}"}), 400

        print(f"Using assistant: {assistant_id} for type: {msg_type}")

        # Run the Assistant
        run = client.beta.threads.runs.create(
            thread_id=thread_id,
            assistant_id=assistant_id
        )

        calendar_event_created = False
        # Check if the Run requires action (function call)
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=thread_id,
                run_id=run.id
            )

            if run_status.status == 'completed':
                break
            elif run_status.status == 'requires_action':
                tool_outputs = []
                for tool_call in run_status.required_action.submit_tool_outputs.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    output = None
                    print(f"Executing function: {function_name}")
                    try:
                        if function_name == "solar_panel_calculations":
                            output = solar.solar_panel_calculations(
                                arguments["address"],
                                arguments["monthly_bill"]
                            )
                        elif function_name == "check_availability":
                            output = calendar_service.check_availability(
                                arguments["start_time"],
                                arguments["end_time"],
                                message=user_input
                            )
                        elif function_name == "create_appointment":
                            output = calendar_service.create_appointment(
                                arguments["summary"],
                                arguments["description"],
                                arguments["start_time"],
                                arguments["end_time"],
                                arguments["email"],
                                message=user_input
                            )
                            calendar_event_created = True
                            print("Kalendereintrag erfolgreich erstellt")

                        if output:
                            tool_outputs.append({
                                "tool_call_id": tool_call.id,
                                "output": json.dumps(output)
                            })

                    except Exception as func_error:
                        print(f"Error in function {function_name}: {str(func_error)}")
                        if calendar_event_created:
                            return jsonify({
                                "response": "Der Termin wurde erfolgreich erstellt. Bitte prüfen Sie Ihre E-Mail für die Details.",
                                "status": "success",
                                "calendar_event": "created"
                            })
                        raise func_error

                if tool_outputs:
                    try:
                        client.beta.threads.runs.submit_tool_outputs(
                            thread_id=thread_id,
                            run_id=run.id,
                            tool_outputs=tool_outputs
                        )
                    except Exception as submit_error:
                        print(f"Error submitting tool outputs: {str(submit_error)}")
                        if calendar_event_created:
                            return jsonify({
                                "response": "Der Termin wurde erfolgreich erstellt. Bitte prüfen Sie Ihre E-Mail für die Details.",
                                "status": "success",
                                "calendar_event": "created"
                            })
                        raise submit_error

            elif run_status.status == 'failed':
                if calendar_event_created:
                    return jsonify({
                        "response": "Der Termin wurde erfolgreich erstellt. Bitte prüfen Sie Ihre E-Mail für die Details.",
                        "status": "success",
                        "calendar_event": "created"
                    })
                return jsonify({"error": "Assistant run failed"}), 500

            time.sleep(1)

        # Wenn wir hier ankommen, war alles erfolgreich
        messages = client.beta.threads.messages.list(thread_id=thread_id)
        response = messages.data[0].content[0].text.value

        return jsonify({
            "response": response,
            "status": "success",
            "calendar_event": "created" if calendar_event_created else "none"
        })

    except Exception as e:
        print(f"Error in chat endpoint: {str(e)}")
        if calendar_event_created:
            return jsonify({
                "response": "Der Termin wurde erfolgreich erstellt. Bitte prüfen Sie Ihre E-Mail für die Details.",
                "status": "success",
                "calendar_event": "created"
            })
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    port = Environment.get_port()
    debug = not Environment.is_production()
    app.run(host='0.0.0.0', port=port, debug=debug)