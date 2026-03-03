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
- Generate ONLY valid SQLite SQL. No explanations, no markdown, no comments.
- Always use SELECT statements only. Never use DROP, DELETE, UPDATE, INSERT, or ALTER.
- Never invent columns. Only use the columns listed in the schema.

Revenue & Measures:
- Use SUM(Sales_USD) for revenue unless the user explicitly asks for local currency.
- If the user asks for local currency, use SUM(Sales_Local) and include the Currency column in the result.
- Display local currency results using the Currency code (e.g., USD, EUR, INR), not generic labels like "currency units".
- Units should use SUM(Units).
- Budget comparisons should use SUM(Budget_USD).

Hierarchy Rules:
- Franchise aggregates all underlying Brands.
- Region aggregates Clusters and Countries.
- Always aggregate unless the user explicitly asks for detailed (brand-level or country-level) output.

Time Logic:
- Use Year and Quarter columns for time filtering.
- Quarter refers to calendar quarters (Q1–Q4).

Percentage & Growth Logic:
- If the question asks for growth, change, variance, or percentage:
  - Calculate as (current - prior) / prior * 100.
  - Name the output column as Percentage.
  - Do not return decimals for percentages.

Formatting Rules:
- Use clear column aliases (e.g., Total_Sales_USD, Percentage).
- Return one result table only.
- Use thousand separator

Interpretation Rules:
- Treat common country abbreviations as equivalent (e.g., US = USA, UK = United Kingdom if present).
- If the question is ambiguous, make a reasonable assumption and generate the most likely SQL.

Output Rules:
- Output SQL only.
- Do not include any explanatory text.

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