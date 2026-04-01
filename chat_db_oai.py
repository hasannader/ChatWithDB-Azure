import streamlit as st
from Build_Client import build_client
from openai import AzureOpenAI
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
from rag_fewshots import query_relevant_chunks
# Load environment variables from .env file
load_dotenv()

# Configuration Constants
DB_URL = os.getenv("DB_URL")

client = build_client()
llm = client


def extract_years_from_dates(invoice_dates):
    """
    Extract unique years from a list of InvoiceDate strings.
    Format: 'M/D/YYYY  hh:mm:ss AM/PM'
    Examples: '1/1/2009  12:00:00 AM', '7/20/2013 12:00:00 AM'
    
    Returns sorted list of unique years as strings.
    """
    import re
    
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
Respond with ONLY the country name (or code if applicable). Examples: USA, Canada, UK

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

#==============================================================================================================================
# Function to Retrieve Database Schema (tables name, columns name, data types and, an example for each value) for Context in Prompts
@st.cache_data
def get_schema():
    engine = get_engine()
    inspector_query = text("""
                        select table_name, column_name, data_type 
                        from information_schema.columns 
                        where table_schema = 'public'   
                        order by table_name, ordinal_position;          
                        """
                        )  
    schema_str = ""
    try:
        with engine.connect() as conn:
            result = conn.execute(inspector_query) 
            current_table = ""
            for row in result :
                table_name, column_name, data_type = row[0], row[1], row[2]

                if table_name != current_table :
                    schema_str += f"\nTable : {table_name}\n Columns: "
                    current_table = table_name

                    # get one sample row.
                    sample_query = text(f'SELECT "{column_name}" FROM "{table_name}" LIMIT 1')
                    sample_row = conn.execute(sample_query).fetchone()
                    sample_row = sample_row if sample_row else None

                # Get value for this column from sample row
                sample_value = None
                if sample_row:
                    sample_value = sample_row[column_name]

                schema_str += f"   - {column_name} ({data_type}) | example: {sample_value}\n"  
                 
    except Exception as e:
        print(f"an error accur {e} ")
   
    return schema_str

#========================================================================================================================
def get_description() -> str:
    schema = get_schema()
    prompt=f"""
        you are an expert postgressSQL data analyst.
        here is the database schema contain tables name, columns name, data type for each column and, an example value for each column in the schema: {schema}.
        Your task:
        1- Write a 2–3 sentence description for EACH column in EACH table.
        2- The description should be based on the column name, data type and the example value provided in the schema.
        3- The description should be concise and informative, it should give a clear idea about the content
    """
    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}]
    )
   
    desc = response.choices[0].message.content

    return desc


#========================================================================================================================

def get_sql_from_openai(question, schema, description, relevant_chunks):
    prompt = f"""
You are a professional Data Analyst with deep expertise in these databases and PostgreSQL.

You understand:
- The structure and relationships within these databases
- Best practices for data analysis and SQL query optimization
- The business context and data semantics
- How to extract meaningful insights from complex datasets

here is the database schema contain tables name, columns name, data type for each column and, 
an example value for each column in the schema, you are working with:
{schema}

here is the description of each column in the databas: {description}
Your task:
1- Write a PostgreSQL query to answer the following question: {question}
2- IMPORTANT: the tables were created via pandas.
   - If columns or tables names are MixedCase, use double quotes around them.
3- CRITICAL: For InvoiceDate (format: 'M/D/YYYY  hh:mm:ss AM/PM'):
   - To extract year: Use regex → (regexp_matches("InvoiceDate", '(\\d{{4}})','g'))[1]::integer
   - To filter by year: Use LIKE → WHERE "InvoiceDate" LIKE '%2009%'
   - Example query: SELECT DISTINCT (regexp_matches("InvoiceDate", '(\\d{{4}})','g'))[1]::integer AS year FROM "Invoice" WHERE "CustomerId" = 23
4- Ensure the query is optimized and handles edge cases properly.
5- Return ONLY the SQL query, without any explanation or comments.

RELEVANT EXAMPLES (for style guidance only - adapt, don't copy):
{relevant_chunks}
"""

    # Generate content from the model
    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2048
    )

    # Clean the markdown formatting (backticks) from the response
    clean_sql = response.choices[0].message.content.replace("```sql", "").replace("```", "").strip()

    return clean_sql
#============================================================================================================

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
You are a professional Data Analyst communicating with a client about their data.

User Question: {question}
Generated SQL Query: {sql}
Data retrieved from the query:
{data}

Task:
- Answer the user's question in a natural language format based on the data retrieved
- Provide clear, professional insights and interpretations
- Highlight important patterns, trends, or anomalies if present
- If the data is empty, say "No results found for this query"
- Be thorough and provide comprehensive analysis
- Keep your response under 500 tokens. Be concise but thorough.
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
    Classify whether the user's question is database-related, system-related, or irrelevant.
    Returns: 'DATABASE', 'SYSTEM', or 'IRRELEVANT'
    """
    prompt = f"""
You are an intelligent question classifier for a Database Chatbot system.

Here is the database schema available:
{schema}

User Question: {question}

Classify this question into ONE of these categories:

1. DATABASE_QUESTION - The user is asking for data/insights from the available databases
   Examples: "How many orders were placed?", "Show me sales by region", "What's the average price?"

2. SYSTEM_QUESTION - The user is asking about how THIS chatbot system works, its features, or capabilities
   Examples: "How does this system work?", "What databases are available?", "Can you help me analyze data?", "What can you do?"

3. IRRELEVANT_QUESTION - The user is asking something completely unrelated to this database system
   Examples: "What's 2+2?", "Tell me a joke", "What's the weather?", "How to bake a cake?"

Respond with ONLY the classification: "DATABASE_QUESTION", "SYSTEM_QUESTION", or "IRRELEVANT_QUESTION"
"""
    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=100
    )
    result = response.choices[0].message.content.strip().upper()
    
    if "DATABASE" in result:
        return "DATABASE"
    elif "SYSTEM" in result:
        return "SYSTEM"
    else:
        return "IRRELEVANT"


def is_database_question(question, schema):
    """
    Classify whether the user's question requires database querying.
    Returns True if it's a database-related question, False otherwise.
    """
    return classify_question(question, schema) == "DATABASE"


def answer_general_question(question):
    """
    Answer system-related questions about this chatbot application.
    """
    prompt = f"""
You are a helpful assistant for a Database Chatbot system that helps users query PostgreSQL databases using natural language.

User Question: {question}

Provide a clear, comprehensive answer about how this database chatbot system works, its features, and capabilities.
Focus on helping the user understand how to use this tool effectively.
Keep your response under 500 tokens. Be concise but thorough.
"""
    response = llm.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
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
            description = get_description()
            # Check for special case: years by country question
            if is_year_by_country_question(prompt):
                st.write("📅 *Extracting invoice years by country...*")
                years, response = get_years_by_country(prompt, schema)
                if years:
                    st.write(f"**Found years:** {', '.join(years)}")
                    
            else:
                # Regular flow: Classify the question
                question_type = classify_question(prompt, schema)
                
                if question_type == "DATABASE":
                    # Database-related question - proceed with SQL generation
                    st.write("📊 *Analyzing your database question...*")
                    relevant_chunks = query_relevant_chunks(prompt)
                    [print(ch) for ch in relevant_chunks]
                    sql_query = get_sql_from_openai(prompt, schema, description, relevant_chunks)
                    
                    with st.expander("Generated SQL Query"):
                        st.code(sql_query, language="sql")
                        
                    query_result = run_query(sql_query)
                    
                    if isinstance(query_result, list):
                        with st.expander("Query Result"):
                            st.table(query_result)
                        response = get_chat_response(prompt, sql_query, query_result)
                    else:
                        response = f"Sorry, I encountered an error: {query_result}"
                        
                elif question_type == "SYSTEM":
                    # System-related question - answer about how this chatbot works
                    st.write("ℹ️ *Answering your system question...*")
                    response = answer_general_question(prompt)
                    
                else:
                    # Irrelevant question - not related to this system
                    st.write("❌ *This question is not relevant to this database system*")
                    response = "I'm a database chatbot designed to help you analyze data in this database system. Your question doesn't relate to this system or the data available. Please ask me questions about:\n- Data in the database (tables, records, analytics)\n- How this database system works\n- Features and capabilities of this chatbot"

            st.markdown(response)
            
        st.session_state.messages.append({"role": "assistant", "content": response})

if __name__ == "__main__":
    main()
