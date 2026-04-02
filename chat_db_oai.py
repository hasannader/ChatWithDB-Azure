import streamlit as st
from openai import AzureOpenAI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import re
from history import get_conversation_history  # <-- Add the conversation history function

# Load environment variables from .env file
load_dotenv()

# Configuration Constants
DB_URL = os.getenv("DB_URL")
AZURE_KEY = os.getenv("AZURE_KEY")



llm = AzureOpenAI(
    azure_endpoint="https://gbgacademy-genai-4.openai.azure.com/",
    api_key=AZURE_KEY,
    api_version="2024-12-01-preview",
)


def extract_years_from_dates(invoice_dates):
    """
    Extract unique years from a list of InvoiceDate strings.
    Format: 'M/D/YYYY  hh:mm:ss AM/PM'
    Examples: '1/1/2009  12:00:00 AM', '7/20/2013 12:00:00 AM'
    
    Returns sorted list of unique years as strings.
    """
    
    if not invoice_dates:
        return []
    
    years = set()
    
    # Pattern to match years (4 consecutive digits after space and date)
    # Looking for YYYY in format like: 1/1/2009 or M/D/YYYY
    year_pattern = r'\d{1,2}/\d{1,2}/(\d{4})'
    
    for date_str in invoice_dates:
        if not date_str:
            continue
        
        try:
            # Extract year using regex
            match = re.search(year_pattern, str(date_str).strip())
            if match:
                year = match.group(1)
                years.add(year)
            else:
                # Fallback: look for any 4-digit number that looks like a year (1900-2100)
                year_match = re.search(r'(19\d{2}|20\d{2})', str(date_str))
                if year_match:
                    years.add(year_match.group(1))
        except Exception as e:
            # Skip problematic dates
            continue
    
    return sorted(list(years))


def is_year_by_country_question(question):
    """
    Detect if the question is asking for years filtered by country.
    Examples: "what are invoice years contains USA", "invoice years for Canada", etc.
    """
    keywords = ["year", "years", "country", "billing", "invoicedate", "when"]
    question_lower = question.lower()
    
    # Check if question has year/years and country keywords
    has_year_keyword = any(kw in question_lower for kw in ["year", "years"])
    has_country_keyword = "country" in question_lower or any(country in question_lower for country in ["usa", "canada", "uk", "germany", "france", "australia"])
    
    return has_year_keyword and has_country_keyword


def get_years_by_country(question, schema):
    """
    Special handler for questions about invoice years by country.
    Returns list of years for the specified country.
    """
    # First, generate a query to get all InvoiceDates for the specified country
    prompt = f"""
Extract the country mentioned in this question: {question}
Respond with ONLY the canonical country name as it commonly appears in databases (e.g. if the user says 'US', 'United States' or 'America', respond with 'USA'. If they say 'UK' or 'Britain', respond with 'United Kingdom'. If they say 'CA', respond with 'Canada').
Examples: USA, Canada, United Kingdom, France, Germany

If no specific country found, respond with: UNKNOWN
"""
    
    country_response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    country = country_response.choices[0].message.content.strip()
    
    if country == "UNKNOWN":
        return None, "Could not identify country in your question"
    
    # Generate SQL to get all InvoiceDates for this country
    sql_prompt = f"""
Generate a PostgreSQL query to get all "InvoiceDate" values where "BillingCountry" = '{country}'

Here is the schema:
{schema}

Return ONLY the SQL query, no explanation.
"""
    
    sql_response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": sql_prompt}]
    )
    
    sql_query = sql_response.choices[0].message.content.replace("```sql", "").replace("```", "").strip()
    
    # Execute the query
    engine = get_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql_query))
            rows = result.fetchall()
            invoice_dates = [row[0] for row in rows if row[0]]
    except Exception as e:
        return None, f"Error executing query: {str(e)}"
    
    # Extract years from the dates
    years = extract_years_from_dates(invoice_dates)
    
    if not years:
        return years, f"No invoices found for {country}"
    
    return years, f"Invoice years for {country}: {', '.join(years)}"

# Streamlit UI Configuration
st.set_page_config(page_title="Postgress SQL Chatbot")
st.title("Chat with DB")

# Database Connection Function
@st.cache_resource
def get_engine():
    return create_engine(DB_URL)

# Function to Retrieve Database Schema for Context in Prompts
@st.cache_data
def get_schema():

    engine=get_engine()
    inspector_query = text("""
                        SELECT table_name, column_name
                        FROM information_schema.columns 
                        WHERE table_schema = 'public'
                        ORDER BY table_name, ordinal_position;
                     """)
    
    schema_str = ""

    try:
        with engine.connect() as conn:
            result = conn.execute(inspector_query)
            current_table = ""
            for row in result:
                table_name, column_name = row[0], row[1]
                if table_name != current_table:
                    schema_str += f"\nTable: {table_name}\nColumns: "
                    current_table = table_name
                schema_str += f"{column_name}, "
    except Exception as e:
        st.error(f"ERROR reading schema: {e}")
    
    return schema_str
def get_sql_from_openai(question, schema, past_messages):
    # Fetch the conversation history to include it in the Prompt as context
    history_context = get_conversation_history(past_messages)
    
    prompt = f"""
You are a professional Data Analyst with deep expertise in PostgreSQL and database querying.

You understand:
- The structure and relationships within the database
- Best practices for SQL query optimization
- How to answer user questions accurately from database data

Here is the database schema:
{schema}

---
{history_context}
---

Your task:
1. Write a PostgreSQL query to answer this user question:
{question}
   (NOTE: Please resolve any pronouns or references in the Current Question using the Previous Conversation History provided above).

2. IMPORTANT: the tables were created via pandas.
   - If table names or column names are MixedCase, use double quotes around them.

3. CRITICAL: For InvoiceDate (format: 'M/D/YYYY  hh:mm:ss AM/PM'):
   - To extract year: Use regex → (regexp_matches("InvoiceDate", '(\\d{{4}})','g'))[1]::integer
   - To filter by year: Use LIKE → WHERE "InvoiceDate" LIKE '%2009%'
   - Example:
     SELECT DISTINCT (regexp_matches("InvoiceDate", '(\\d{{4}})','g'))[1]::integer AS year
     FROM "Invoice"
     WHERE "CustomerId" = 23

4. COUNTRY NAMES RULES (VERY IMPORTANT):
   - The database stores country names specifically (e.g., 'USA', 'Canada', 'United Kingdom').
   - If the user asks about 'US', 'USA', 'America', 'United States', YOU MUST use an IN clause: IN ('USA', 'US', 'United States', 'America')
   - For 'Canada' / 'CA', use IN ('Canada', 'CA').
   - For 'United Kingdom' / 'UK', use IN ('United Kingdom', 'UK', 'Britain').

5. LIMIT RULES (VERY IMPORTANT):
   - If the user asks for a specific number like:
     "top 3", "first 5", "highest 7", "show 20", "give me 15"
     → use LIMIT with that exact number.
   - If the user clearly asks for ALL results using words like:
     "all", "everything", "list all", "show all"
     → DO NOT use LIMIT.
   - If the user does NOT specify how many rows they want
     → use LIMIT 10 by default.
   - If the question is an aggregate query that naturally returns one row
     (like COUNT, SUM, AVG, MAX, MIN)
     → do NOT force LIMIT 10 unless needed.

6. If the user asks for "top", "highest", "best", "most", "largest"
   → make sure to ORDER BY appropriately in descending order.

7. If the user asks for "lowest", "least", "smallest", "bottom"
   → make sure to ORDER BY appropriately in ascending order.

8. Ensure the query is optimized and handles edge cases properly.

9. Return ONLY the SQL query, with no explanation and no markdown.
"""

    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048
    )

    clean_sql = response.choices[0].message.content.replace("```sql", "").replace("```", "").strip()
    return clean_sql

def run_query(sql):
    engine = get_engine()
    with engine.connect() as conn:
        try:
            result = conn.execute(text(sql))
            return [dict(row) for row in result.mappings()]
        except Exception as e:
            return str(e)
        



def extract_table_column_info(sql):
    """
    Extract table and column names from the SQL query.
    """
    import re
    
    sql_upper = sql.upper()
    info_parts = []
    
    # Extract table names (FROM clause)
    from_match = re.search(r'FROM\s+(["\']?\w+["\']?(?:\s*,\s*["\']?\w+["\']?)*)', sql_upper)
    if from_match:
        tables = from_match.group(1)
        # Clean up the table names
        tables_clean = re.findall(r'["\']?(\w+)["\']?', tables)
        if tables_clean:
            info_parts.append(f"**Tables:** {', '.join(tables_clean)}")
    
    # Extract column names (SELECT clause)
    select_match = re.search(r'SELECT\s+(.*?)\s+FROM', sql_upper)
    if select_match:
        columns_str = select_match.group(1)
        # Remove functions, get column names
        columns = re.findall(r'["\']?(\w+)["\']?(?:\s+AS|,|\s|$)', columns_str)
        if columns and columns[0] != '*':
            info_parts.append(f"**Columns:** {', '.join(set(columns))}")
    
    return " | ".join(info_parts) if info_parts else ""




def classify_question(question, schema):
    """
    Classify whether the user's question is:
    - DATABASE
    - CHAT
    - GENERAL

    DATABASE = asks about Chinook database data
    CHAT = greetings, thanks, vague help, assistant capability
    GENERAL = unrelated factual/general world questions
    """
    prompt = f"""
You are an intent classifier for a Chinook database chatbot.

The chatbot is ONLY meant to:
1) Chat casually with the user
2) Answer questions about the Chinook database

Here is the database schema:
{schema}

User Question:
{question}

Classify the user message into EXACTLY ONE of these 3 categories:

1. CHAT
Use CHAT ONLY if the message is clearly:
- greeting (hi, hello, good morning)
- thanks or appreciation
- asking what the assistant can do
- vague help like "help", "can you help me?"
- casual conversational message not asking for outside factual knowledge

Examples:
- "hi"
- "hello"
- "thanks"
- "what can you do?"
- "help me"

2. DATABASE
Use DATABASE if the user is asking about:
- data that may exist in the Chinook database
- customers, invoices, artists, albums, tracks, sales, employees, countries, genres, etc.
- analytics, counts, comparisons, trends, top/bottom values

Examples:
- "how many customers are in USA?"
- "top 5 artists"
- "which country has the most invoices?"
- "show me albums by Queen"

3. GENERAL
Use GENERAL if the question is NOT chat and NOT about the Chinook database.
This includes:
- celebrities
- weather
- news
- math
- coding theory
- jokes
- science
- history
- religion
- politics
- sports
- general world knowledge

Examples:
- "who is mohamed salah?"
- "what's the weather?"
- "tell me a joke"
- "what is python?"
- "what is machine learning?"

Important rules:
- If it asks for specific data from the database → DATABASE
- If it is just friendly conversation → CHAT
- If it is asking for outside/general knowledge → GENERAL

Respond with ONLY ONE word:
DATABASE
CHAT
GENERAL
"""

    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=50
    )

    result = response.choices[0].message.content.strip().upper()

    if "DATABASE" in result:
        return "DATABASE"
    elif "CHAT" in result:
        return "CHAT"
    else:

        return "GENERAL"
    


def answer_general_question(question):
    """
    Politely refuse unrelated general-purpose questions.
    """
    prompt = f"""
You are a friendly assistant inside a Chinook database chat application.

The user asked:
{question}

This question is NOT related to the database system and should NOT be answered.

Your job:
- Politely and warmly explain that you are only meant to help with the Chinook database
- Do NOT answer the user's actual question
- Sound friendly, natural, and non-robotic
- Keep it short and helpful
- Encourage the user to ask about the database instead

Examples of good style:
- "I’m mainly here to help with the Chinook database, so I can’t really answer that one. But feel free to ask me about customers, invoices, artists, albums, or sales."
- "That’s outside my scope — I’m focused on the Chinook database only. If you want, ask me something about the data and I’ll help."

Do NOT mention SQL unless necessary.
Do NOT answer the general question itself.
"""

    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )

    return response.choices[0].message.content.strip()


def answer_chat_question(question):
    """
    Handle greetings, thanks, vague help, and capability questions.
    """
    prompt = f"""
You are a friendly conversational assistant for a Chinook database chat application.

Your role is to chat naturally with the user when their message does NOT require querying the database.

Behavior guidelines:

1. Greetings & small talk
   - Greet the user warmly
   - Be friendly, polite, and approachable

2. Offer help proactively
   - Mention that you can help explore the Chinook database
   - Encourage questions about artists, albums, tracks, customers, invoices, employees, etc.

3. Stay concise
   - Keep responses short and conversational
   - Avoid long explanations unless asked

4. Do NOT generate or mention SQL
   - If the user is chatting casually, never talk about technical details

5. Handle vague questions
   - If user says "help" or "can you help me?" → guide them gently

6. Handle appreciation
   - If user says "thanks" → respond politely

7. Handle capability questions
   - If user asks what you can do → explain briefly

Tone:
- Friendly
- Supportive
- Natural
- Non-robotic
- Professional but casual

User message:
{question}

Respond naturally and briefly.
"""

    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200
    )

    return response.choices[0].message.content.strip()



def get_chat_response(question, sql, data, past_messages):
    # Fetch the conversation history for the final response so it remains contextual
    history_context = get_conversation_history(past_messages)
    
    prompt = f"""
You are a friendly data assistant helping a user understand results from the Chinook database.

---
{history_context}
---

User Question: {question}
Generated SQL Query: {sql}
Data retrieved from the query:
{data}

Task:
- Answer the question in a natural, human-like sentence
- Start with the answer directly, but phrase it conversationally
- Avoid robotic or fragmented sentences
- Do NOT start with phrases like "Based on the data" or "The query shows"
- Keep it concise and smooth
- Please consider the context from the Previous Conversation History when forming your answer if necessary.
"""

    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )

    answer = response.choices[0].message.content.strip()

    # Extract table and column info from SQL
    table_col_info = extract_table_column_info(sql)
    if table_col_info:
        answer += f"\n\n**Source Information:**\n{table_col_info}"

    return answer

def main():
    # Main app logic
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask anything about the Chinook database..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            schema = get_schema()
            
            # Check for special case: years by country question
            if is_year_by_country_question(prompt):
                st.write("📅 *Extracting invoice years by country...*")
                years, response = get_years_by_country(prompt, schema)
                if years:
                    st.write(f"**Found years:** {', '.join(years)}")
                    
            else:
                # Regular flow: classify the question
                question_type = classify_question(prompt, schema)

                if question_type == "DATABASE":
                    # Database-related question - proceed with SQL generation
                    st.write("📊 *Analyzing your database question...*")
                    # Extract only past messages without the current question
                    past_messages = st.session_state.messages[:-1]
                    
                    sql_query = get_sql_from_openai(prompt, schema, past_messages)

                    with st.expander("Generated SQL Query"):
                        st.code(sql_query, language="sql")

                    query_result = run_query(sql_query)

                    if isinstance(query_result, list):
                        with st.expander("Query Result"):
                            st.table(query_result)

                        if len(query_result) == 0:
                            response = (
                                "I couldn’t find matching data for that in the Chinook database. "
                                "Try rephrasing it or asking about customers, invoices, artists, albums, tracks, or sales."
                            )
                        else:
                            response = get_chat_response(prompt, sql_query, query_result, past_messages)
                    else:
                        response = (
                            "I couldn’t answer that from the Chinook database. "
                            "Try rephrasing your question or asking about customers, invoices, artists, albums, tracks, or sales."
                        )

                elif question_type == "CHAT":
                    # Friendly conversational messages
                    st.write("💬 *Chatting with you...*")
                    response = answer_chat_question(prompt)

                else:
                    # General-purpose unrelated questions
                    st.write("🚫 *That’s outside this chatbot’s scope*")
                    response = answer_general_question(prompt)
            st.markdown(response)
            
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
