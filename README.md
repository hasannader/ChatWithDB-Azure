<!--
Description: PostgreSQL Chat Database is a Streamlit-powered chatbot using Azure OpenAI's GPT-4o. Transform natural language questions into SQL queries instantly. Perfect for data analysts and developers seeking database interactions without writing SQL. Features automatic schema detection, query visualization, and AI-powered responses.
-->

# PostgreSQL Chat Database

A Streamlit-based chatbot application that leverages Azure OpenAI's GPT-4o model to interact with PostgreSQL databases through natural language queries.

## Features

- **Natural Language to SQL**: Ask questions in plain English and get SQL queries automatically generated
- **Direct Database Interaction**: Execute queries and retrieve results from PostgreSQL databases
- **Conversation History**: Maintain chat history within a session
- **Query Visualization**: View generated SQL queries before execution
- **Result Display**: View query results in a formatted table
- **AI-Powered Responses**: Get natural language answers based on database query results

## Prerequisites

- Python 3.12+
- PostgreSQL database
- Azure OpenAI API credentials
- Virtual environment (recommended)

## Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd DB_chat_clone
```

### 2. Create Virtual Environment
```bash
python -m venv venv
```

### 3. Activate Virtual Environment

**Windows:**
```bash
venv\Scripts\activate
```

**macOS/Linux:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Create a `.env` file in the project root directory with the following variables:

```env
# Azure OpenAI Configuration
AZURE_OPENAI_API_KEY=your_azure_openai_api_key
AZURE_OPENAI_ENDPOINT=your_azure_openai_endpoint
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_MODEL=gpt-4o
AZURE_OPENAI_TIMEOUT=30

# Database Configuration
DB_URL=postgresql://user:password@localhost:5432/database_name
```

### Configuration Details

- **AZURE_OPENAI_API_KEY**: Your Azure OpenAI API key
- **AZURE_OPENAI_ENDPOINT**: Your Azure OpenAI service endpoint
- **AZURE_OPENAI_API_VERSION**: API version (default: 2024-12-01-preview)
- **AZURE_OPENAI_MODEL**: Model name (default: gpt-4o)
- **AZURE_OPENAI_TIMEOUT**: Request timeout in seconds (default: 30)
- **DB_URL**: PostgreSQL connection string in format: `postgresql://user:password@host:port/database`

## Usage

### Run the Application

```bash
streamlit run chat_db_oai.py
```

The application will open in your default browser at `http://localhost:8501`

### How to Use

1. **Start the Application**: Run the command above
2. **Ask a Question**: Type your question in the chat input (e.g., "How many orders were placed in 2023?")
3. **View Generated SQL**: Check the "Generated SQL Query" section to see the SQL that was created
4. **View Results**: Check the "Query Result" section to see the database results
5. **Read Response**: The AI-powered assistant will provide a natural language answer based on the results

## Project Structure

```
DB_chat_clone/
├── chat_db_oai.py          # Main Streamlit application (Azure OpenAI GPT-4o)
├── chat_db_gemini.py       # Alternative version using Google Gemini API
├── azure_oai_4o.py         # Azure OpenAI client configuration
├── deploy.py               # Database deployment script for Railway
├── databases/              # Contains database files and configurations
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not included in repo)
└── README.md               # This file
```

The project provides two versions with different AI backends:

- **chat_db_oai.py** (Default): Uses Azure OpenAI's GPT-4o model for SQL generation and natural language responses
- **chat_db_gemini.py** (Alternative): Uses Google's Gemini API as an alternative backend for the same functionality

Both versions support the same database operations and UI features. Choose based on your API preferences and availability.

## Key Features Explained

### Database Schema Detection
The application automatically retrieves your PostgreSQL database schema and provides it as context to the AI model for generating accurate SQL queries.

### Query Execution
Generated SQL queries are executed against your PostgreSQL database, with proper error handling for invalid queries.

### Natural Language Processing
Azure OpenAI's GPT-4o model understands complex questions and generates production-ready SQL queries, including:
- Handling MixedCase column names with proper quoting
- Date/time string manipulation
- Complex filtering and aggregation

## Important Notes

- **Table Creation**: This application assumes tables were created via pandas. MixedCase table and column names are automatically quoted in generated queries.
- **Date Handling**: The "InvoiceDate" column is expected to be a string format (e.g., '7/20/2013 12:00:00 AM'). The AI automatically handles year extraction and casting.
- **Error Handling**: If a query fails, the application displays the error message for debugging.

## Dependencies

Main dependencies include:
- `streamlit`: Web application framework
- `openai`: Azure OpenAI client library
- `sqlalchemy`: SQL toolkit and ORM
- `python-dotenv`: Environment variable management
- `psycopg2`: PostgreSQL database adapter

For a complete list, see `requirements.txt`

## Troubleshooting

### Missing API Key Error
**Error**: `ValueError: Missing AZURE_OPENAI_API_KEY in .env`
- **Solution**: Ensure your `.env` file contains the correct `AZURE_OPENAI_API_KEY`

### Database Connection Error
**Error**: `sqlalchemy.exc.OperationalError`
- **Solution**: Verify your `DB_URL` is correct and the PostgreSQL database is running

### No Results Found
- Check if your question matches the database schema
- View the generated SQL query to verify it's correct
- Test the query directly in PostgreSQL if needed

## Limitations

- The AI model may not generate perfect SQL for all complex queries
- Some advanced database features may not be supported
- Query performance depends on database size and complexity

## Future Enhancements

- Support for multiple database types
- Query performance optimization suggestions
- Ability to save and rerun queries
- User authentication
- Database backup integration

## License

This project is provided as-is for educational and professional purposes.

## Support

For issues or questions, please refer to the project documentation or contact the development team.

---

**Last Updated**: March 27, 2026
