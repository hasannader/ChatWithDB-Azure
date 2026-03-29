import streamlit as st
from azure_oai_4o import build_client
from openai import AzureOpenAI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Configuration Constants
DB_URL = os.getenv("DB_URL")

# Replace Google Generative AI with Azure OpenAI GPT-4o
client = build_client()
llm = client

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

def get_sql_from_openai(question, schema):
    prompt = f"""
You are an expert PostgreSQL Data Analyst.

Here is the database schema:
{schema}

Your task:
1- Write a PostgreSQL query to answer the following question: {question}
2- IMPORTANT: the tables were created via pandas.
   -If columns or tables names are MixedCase, use double quotes around them.
3- The "InvoiceDate" column is a string. When you need to filter by year, you must extract the year from this string and cast it to an integer. For example:
   - If "InvoiceDate" is '7/20/2013 12:00:00 AM', the year is 2013.
   - If "InvoiceDate" is '2/2/2009 12:00:00 AM', the year is 2009.
4- Return ONLY the SQL query, without any explanation or comments.
"""

    # Generate content from the model
    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )

    # Clean the markdown formatting (backticks) from the response
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
        
def get_chat_response(question, sql, data):
    prompt = f"""
User Question: {question}
Generated SQL Query: {sql}
Data retrieved from the query:
{data}

Task: Answer the user's question in a naturel language format based on the data retrieved.
If the data is empty, say "No results found".
"""
    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def main():
    # Main app logic
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("What is up?"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            schema = get_schema()
            sql_query = get_sql_from_openai(prompt, schema)
            
            with st.expander("Generated SQL Query"):
                st.code(sql_query, language="sql")
                
            query_result = run_query(sql_query)
            
            if isinstance(query_result, list):
                with st.expander("Query Result"):
                    st.table(query_result)
                response = get_chat_response(prompt, sql_query, query_result)
            else:
                response = f"Sorry, I encountered an error: {query_result}"

            st.markdown(response)
            
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()