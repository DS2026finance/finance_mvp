import streamlit as st
import sqlite3
import pandas as pd
from openai import OpenAI
import plotly.express as px
import plotly.graph_objects as go

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
- Use SUM(Budget_USD) for budget comparisons
- If the question contains "variance" or "revenue variance", always return both Sales_USD and Budget_USD.
- Display local currency results using the Currency code (e.g., USD, EUR, INR).
- Units should use SUM(Units).

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

Interpretation Rules:
- Treat common country abbreviations as equivalent (e.g., US = USA, UK = United Kingdom if present).
- If the question is ambiguous, make a reasonable assumption and generate the most likely SQL.
- Brand A should be treated as one word. Same as Franchise A.
- If the question contains "variance", "difference", or "revenue variance", always return both Sales_USD and Budget_USD columns in the SQL output.

Output Rules:
- Output SQL only.
- If the question is ambiguous or cannot be answered from the available columns, do NOT generate SQL. Instead, respond with: "I don't understand the question. Please rephrase."
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

    # If the model returns "I don't understand", handle gracefully
    if "I don't understand" in sql_query:
        st.info(sql_query)
        st.stop()

    # Simple safety check
    forbidden = ["drop", "delete", "update", "insert"]
    if not sql_query.lower().startswith("select") or any(word in sql_query.lower() for word in forbidden):
        st.error("Unsafe or invalid SQL generated. Please rephrase your question.")
        st.stop()

    # Execute SQL safely
    try:
        df = pd.read_sql_query(sql_query, conn)
    except:
        st.info("I don't understand the question. Please rephrase.")
        st.stop()

    if df.empty:
        st.info("Query returned no data.")
        st.stop()
        
    df_chart = df.copy()
        
    # Format numeric columns (thousand separator), excluding Year/Quarter/Month
    numeric_cols = df.select_dtypes(include=['float64', 'int64']).columns.tolist()
    time_cols = [col for col in numeric_cols if any(word in col.lower() for word in ["year","quarter","month","date"])]
    format_cols = [col for col in numeric_cols if col not in time_cols]

    for col in format_cols:
        df[col] = df[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")
        
    # Format percentage columns
    percentage_cols = [col for col in df.columns if "percent" in col.lower() or "growth" in col.lower()]
    for col in percentage_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce') # convert to numeric
        df[col] = df[col].map(lambda x: f"{x:.2f}%" if pd.notnull(x) else "")
        
    st.dataframe(df)

    st.subheader("📈 Visualization")

    show_chart = st.toggle("Show Chart")

    if show_chart:

        # Convert numeric columns
        for col in df_chart.columns:
            df_chart[col] = pd.to_numeric(df_chart[col], errors='ignore')

        numeric_cols_chart = df_chart.select_dtypes(include=['float64','int64']).columns.tolist()
        categorical_cols = df_chart.select_dtypes(include=['object']).columns.tolist()

        # Handle Year + Quarter combined
        if 'Year' in df_chart.columns and 'Quarter' in df_chart.columns:
            df_chart['Year_Quarter'] = df_chart['Year'].astype(str) + '-Q' + df_chart['Quarter'].astype(str)
            x_col = 'Year_Quarter'
            df_chart = df_chart.sort_values(by=['Year','Quarter'])
        elif time_cols:
            x_col = time_cols[0]
            df_chart = df_chart.sort_values(by=x_col)
        elif categorical_cols:
            x_col = categorical_cols[0]
        else:
            x_col = df_chart.columns[0]

        # Pick Y column (exclude Year/Quarter)
        y_col_candidates = [col for col in numeric_cols_chart if col not in ['Year','Quarter']]
        if not y_candidates:
            st.info("No numeric data available to visualize.")
        else:
            y_col = y_candidates[0]

            # --- Waterfall if Sales vs Budget present ---
            if 'Sales_USD' in df_chart.columns and 'Budget_USD' in df_chart.columns:
                df_chart['Variance'] = df_chart['Sales_USD'] - df_chart['Budget_USD']
                fig = go.Figure(go.Waterfall(
                    name='Variance',
                    x=df_chart[x_col],
                    y=df_chart['Variance'],
                    measure=['relative']*len(df_chart),
                    text=df_chart['Variance'].apply(lambda x: f"${x:,.0f}"),
                    textposition='outside'
                ))
                fig.update_layout(title='Sales vs Budget Waterfall', yaxis_title='USD', xaxis_title=x_col)
                st.plotly_chart(fig, use_container_width=True)

            # --- Pie chart for percentages ---
            elif any(word in y_col.lower() for word in ['percent','share','mix']):
                fig = px.pie(df_chart, names=x_col, values=y_col, hole=0.4, title=f"{y_col} by {x_col}")
                st.plotly_chart(fig, use_container_width=True)

            # --- Line chart for time series ---
            elif any(word in x_col.lower() for word in ['year','quarter','month','date']):
                fig = px.line(df_chart, x=x_col, y=y_col, markers=True, title=f"{y_col} over {x_col}")
                fig.update_yaxes(tickformat=",")
                st.plotly_chart(fig, use_container_width=True)

            # --- Bar chart for categorical comparisons ---
            else:
                fig = px.bar(df_chart, x=x_col, y=y_col, title=f"{y_col} by {x_col}")
                fig.update_yaxes(tickformat=",")
                st.plotly_chart(fig, use_container_width=True)
    # Ask OpenAI to explain results
    explanation_prompt = f"Explain this result in plain business language:\n{df.to_string(index=False)}"
    explanation = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":explanation_prompt}]
    )

    st.subheader("Explanation")
    st.write(explanation.choices[0].message.content)
        st.subheader("Explanation")
        st.write(explanation.choices[0].message.content)