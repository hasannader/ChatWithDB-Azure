# This script is responsible for handling the conversation history (previous questions and answers)

def get_conversation_history(messages):
    """
    This function receives the list of messages stored in the session_state and formats it into text.
    The goal is to remind the model (LLM) of what was previously asked and answered,
    so the model can understand context-dependent questions.
    For example: "Which country is he from?" following the question "Who is the customer that bought the most?".
    """
    # If the list is empty (first question from the user), return a string indicating no history
    if not messages:
        return "No previous conversation history."
    
    # Take only the last 10 messages (5 questions and 5 assistant answers)
    recent_messages = messages[-10:]
    
    history_text = "Previous Conversation History:\n"
    # Iterate through each message, identify the sender, and add it to the aggregated text
    for msg in recent_messages:
        if msg["role"] == "user":
            history_text += f"User: {msg['content']}\n"
        elif msg["role"] == "assistant":
            history_text += f"Assistant: {msg['content']}\n"
            
    return history_text.strip()
