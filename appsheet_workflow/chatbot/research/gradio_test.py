import gradio as gr
import openai
from dotenv import load_dotenv
import os

# Load the environment variables (API key) from the .env file
load_dotenv()

# Set the OpenAI API key from environment variables
openai.api_key = os.getenv('OPENAI_API_KEY')

# Initial prompt for the AI system
messages = [
    {"role": "system", "content": "You are a Therapist, act as caring and understanding as possible"}
]

def transcribe(audio):
    global messages

    # Open the audio file provided by Gradio
    audio_file = open(audio, "rb")
    # Use OpenAI's Whisper API to transcribe the audio file
    transcript = openai.Audio.transcribe("whisper-1", audio_file)
    
    # Print the transcript to debug
    print(transcript)
    
    # Add the user's transcribed message to the conversation history
    messages.append({"role": "user", "content": transcript["text"]})
    
    # Generate a response from the OpenAI chat model
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages
    )
    
    # Extract the assistant's response and append it to the message history
    system_message = response["choices"][0]["message"]["content"]
    messages.append({"role": "assistant", "content": system_message})

    # Create a chat transcript by looping through the messages
    chat_transcript = ""
    for message in messages:
        if message['role'] != 'system':  # Skip the system message in the output
            chat_transcript += message['role'] + ": " + message['content'] + "\n\n"

    return chat_transcript

# Create the Gradio interface
# Removed the 'source' parameter from gr.Audio
ui = gr.Interface(fn=transcribe, inputs=gr.Audio(type="filepath"), outputs="text")

# Launch the interface and share it publicly
ui.launch(share=True)
