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
        
        df_chart = df.copy()

        # Format percentage columns
        percentage_cols = [col for col in df.columns if "percent" in col.lower() or "growth" in col.lower()]
        for col in percentage_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce') # convert to numeric
            df[col] = df[col].map(lambda x: f"{x:.2f}%")

        # List columns to format with thousand separators
        numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns

        for col in numeric_cols:
            df[col] = df[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
        
        st.dataframe(df)

        st.subheader("📈 Visualization")

        show_chart = st.toggle("Show Chart")

        if show_chart:

            import plotly.express as px

            # Automatically detect numeric columns
            numeric_cols_chart = df_chart.select_dtypes(include=['float64', 'int64']).columns
            categorical_cols_chart = df_chart.select_dtypes(include=['object']).columns

            if len(numeric_cols_chart) >= 1:

                y_col = numeric_cols_chart[0]

                # If we have a categorical column, use it for X
                if len(categorical_cols_chart) >= 1:
                    x_col = categorical_cols_chart[0]
                    fig = px.bar(df_chart, x=x_col, y=y_col, title=f"{y_col} by {x_col}")
                else:
                    fig = px.line(df_chart, y=y_col, title=f"{y_col} Trend")

                fig.update_layout(yaxis_tickformat=",")
                st.plotly_chart(fig, use_container_width=True)

            else:
                st.info("No numeric data available to visualize.")

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