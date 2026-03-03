import streamlit as st
import sqlite3
import pandas as pd
from openai import OpenAI

# Initialize OpenAI client (make sure your API key is set in environment variables)
client = OpenAI()

# Connect to your SQLite database
conn = sqlite3.connect("sales.db")

st.title("📊 Finance Q&A Bot")

question = st.text_input("Ask a finance question:")

def build_prompt(question):
    return f"""
You are a senior finance analyst.

Generate ONLY valid SQLite SQL.
No explanation. No markdown.

Table: sales_data

Columns:
- Month (date)
- Year (integer)
- Quarter (integer)
- Region (text)
- Cluster (text)
- Country (text)
- Franchise (text)
- Brand (text)
- Currency (text)
- Sales_Local (float)
- Sales_USD (float)
- Units (integer)
- Budget_USD (float)

Rules:
- Use SUM(Sales_USD) for revenue
- Franchise aggregates brands
- Budget vs Actual comparisons allowed
- Never invent columns
- Output SQL only

Question:
{question}
"""

if question:
    prompt = build_prompt(question)

    # Ask OpenAI to generate SQL
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    sql_query = response.choices[0].message.content.strip()

    st.subheader("Generated SQL")
    st.code(sql_query)

    # Simple safety check
    forbidden = ["drop", "delete", "update", "insert"]
    if not sql_query.lower().startswith("select"):
        st.error("Invalid SQL")
    elif any(word in sql_query.lower() for word in forbidden):
        st.error("Unsafe SQL")
    else:
        # Run SQL
        df = pd.read_sql_query(sql_query, conn)
        st.dataframe(df)

        # Ask OpenAI to explain results
        explanation_prompt = f"""
Explain this result in plain business language:

{df.to_string(index=False)}
"""
        explanation = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": explanation_prompt}]
        )

        st.subheader("Explanation")
        st.write(explanation.choices[0].message.content)