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

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role":"user","content":prompt}]
    )

    sql_query = response.choices[0].message.content.strip()
    st.subheader("Generated SQL")
    st.code(sql_query)

    if "I don't understand" in sql_query:
        st.info(sql_query)
        st.stop()

    forbidden = ["drop","delete","update","insert"]
    if not sql_query.lower().startswith("select") or any(word in sql_query.lower() for word in forbidden):
        st.error("Unsafe or invalid SQL generated. Please rephrase your question.")
        st.stop()

    try:
        df = pd.read_sql_query(sql_query, conn)
    except:
        st.info("I don't understand the question. Please rephrase.")
        st.stop()

    if df.empty:
        st.info("Query returned no data.")
        st.stop()

    df_chart = df.copy()
    # Format numeric columns
    numeric_cols = df.select_dtypes(include=['float64','int64']).columns.tolist()
    time_cols = [c for c in numeric_cols if any(w in c.lower() for w in ['year','quarter','month','date'])]
    format_cols = [c for c in numeric_cols if c not in time_cols]
    for col in format_cols:
        df[col] = df[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")

    st.dataframe(df)

    st.subheader("📈 Visualization")
    show_chart = st.toggle("Show Chart")

    if show_chart:
        for col in df_chart.columns:
            df_chart[col] = pd.to_numeric(df_chart[col], errors='ignore')

        # X-axis: handle Year + Quarter
        if 'Year' in df_chart.columns and 'Quarter' in df_chart.columns:
            df_chart['X_Label'] = df_chart['Year'].astype(str) + '-Q' + df_chart['Quarter'].astype(str)
        elif 'Year' in df_chart.columns and 'Month' in df_chart.columns:
            df_chart['X_Label'] = df_chart['Year'].astype(str) + '-' + df_chart['Month'].astype(str).str.zfill(2)
        elif 'Quarter' in df_chart.columns:
            # Only Quarter available, prepend placeholder year or leave just Q
            df_chart['X_Label'] = 'Q' + df_chart['Quarter'].astype(str)
        elif 'Month' in df_chart.columns:
            df_chart['X_Label'] = df_chart['Month'].astype(str).str.zfill(2)
        else:
            categorical_cols = df_chart.select_dtypes(include=['object']).columns.tolist()
            df_chart['X_Label'] = df_chart[categorical_cols[0]] if categorical_cols else df_chart.columns[0]


        # --- WATERFALL for Sales vs Budget ---
        if 'Total_Sales_USD' in df_chart.columns and 'Total_Budget_USD' in df_chart.columns:
            sales_col = 'Total_Sales_USD'
            budget_col = 'Total_Budget_USD'
            df_chart['Variance'] = df_chart[sales_col] - df_chart[budget_col]

            if 'X_Label' not in df_chart.columns:
                df_chart['X_Label'] = df_chart.index.astype(str)  # fallback

            x_waterfall = df_chart['X_Label'].tolist()
            y_waterfall = df_chart['Variance'].tolist()
            measures = ['relative'] * len(df_chart)  # all bars are relative (variance)
            texts = [f"${v:,.0f}" for v in df_chart['Variance']]
            
            fig = go.Figure(go.Waterfall(
                x=x_waterfall,
                y=y_waterfall,
                measure=measures,
                text=texts,
                textposition="outside",
                connector={"line":{"color":"gray"}}
            ))
            fig.update_layout(title="Variance: Sales vs Budget", yaxis_title="USD")
            fig.update_yaxes(tickprefix="$", tickformat=",")  # show full USD amounts
            st.plotly_chart(fig, use_container_width=True)

        # --- OTHER CHARTS ---
        y_candidates = [c for c in df_chart.select_dtypes(include=['float64','int64']).columns if c not in ['Year','Quarter','Month']]
        if y_candidates:
            y_col = y_candidates[0]

            # Ensure x-axis exists
            if 'X_Label' in df_chart.columns:
                x_col_plot = 'X_Label'
            else:
                categorical_cols = df_chart.select_dtypes(include=['object']).columns.tolist()
                x_col_plot = categorical_cols[0] if categorical_cols else df_chart.index

            # Ensure x_col_plot is string for plotting
            df_chart[x_col_plot] = df_chart[x_col_plot].astype(str)

            # Decide chart type
            time_keywords = ['year', 'quarter', 'month', 'date']
            if any(k in x_col_plot.lower() for k in time_keywords):
                fig = px.line(df_chart, x=x_col_plot, y=y_col, markers=True, title=f"{y_col} over {x_col_plot}")
                fig.update_yaxes(tickformat=",")
            elif any(word in y_col.lower() for word in ['percent','share','mix']):
                fig = px.pie(df_chart, names=x_col_plot, values=y_col, hole=0.4, title=f"{y_col} by {x_col_plot}")
            else:
                fig = px.bar(df_chart, x=x_col_plot, y=y_col, title=f"{y_col} by {x_col_plot}")
                fig.update_yaxes(tickformat=",")
            st.plotly_chart(fig, use_container_width=True)
    # Explain result
    explanation_prompt = f"Explain this result in plain business language:\n\n{df.to_string(index=False)}"
    explanation = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": explanation_prompt}]
    )
    st.subheader("Explanation")
    st.write(explanation.choices[0].message.content)