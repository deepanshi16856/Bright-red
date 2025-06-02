import google.generativeai as genai
import os
import json
from dotenv import load_dotenv
import difflib

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=API_KEY)

# Gemini model with domain-specific system prompt
model = genai.GenerativeModel(
    "models/gemini-1.5-flash",
    system_instruction="You are an expert assistant for an organ donation website. Only answer questions related to organ donation, recipient and donor registration, awareness, and medical guidelines."
)

# Load FAQ data
with open("faq_data.json", "r") as f:
    faq_data = json.load(f)

# Improved FAQ matching using sentence similarity
def match_faq(user_message):
    user_message = user_message.lower()
    questions = [faq["question"].lower() for faq in faq_data]
    closest_match = difflib.get_close_matches(user_message, questions, n=1, cutoff=0.6)

    if closest_match:
        for faq in faq_data:
            if faq["question"].lower() == closest_match[0]:
                return faq["answer"]
    return None

# Generate chatbot reply
def get_bot_reply(user_message):
    # First try to answer from FAQs
    faq_answer = match_faq(user_message)
    if faq_answer:
        return faq_answer

    # Otherwise, generate with Gemini
    try:
        response = model.generate_content(user_message)
        if hasattr(response, "text") and response.text:
            return response.text
        else:
            return "I'm sorry, I couldn't generate a response."
    except Exception as e:
        print("Gemini API error:", e)
        return "There was an error generating a response. Please try again later."

