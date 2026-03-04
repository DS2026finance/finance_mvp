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

Interpretation Rules:
- Treat common country abbreviations as equivalent (e.g., US = USA, UK = United Kingdom if present).
- If the question is ambiguous, make a reasonable assumption and generate the most likely SQL.
- Brand A should be treated as one word. Same as Franchise A.

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
        st.write("DEBUG: Columns in dataframe")
        st.write(df.columns.tolist())
        
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
            import plotly.graph_objects as go

            # Convert numeric columns
            for col in df_chart.columns:
                df_chart[col] = pd.to_numeric(df_chart[col], errors='ignore')

            numeric_cols = df_chart.select_dtypes(include=['float64', 'int64']).columns
            categorical_cols = df_chart.select_dtypes(include=['object']).columns

            # Detect columns
            sales_col = None
            budget_col = None
            for col in df_chart.columns:
                if "sales" in col.lower() and "budget" not in col.lower():
                    sales_col = col
                if "budget" in col.lower():
                    budget_col = col

            if sales_col and budget_col and len(categorical_cols) >= 1:
                # Create waterfall
                x_col = categorical_cols[0]
                
                df_chart["Variance"] = df_chart[sales_col] - df_chart[budget_col]
                
                # Sort time if X-axis is month/quarter/year
                if any(word in x_col.lower() for word in ["month", "quarter", "year"]):
                    df_chart = df_chart.sort_values(by=x_col)
                
                fig = go.Figure(go.Waterfall(
                    name = "Variance",
                    x = df_chart[x_col],
                    y = df_chart["Variance"],
                    measure = ["relative"]*len(df_chart),
                    text = df_chart["Variance"].apply(lambda x: f"${x:,.0f}"),
                    textposition = "outside"
                ))

                fig.update_layout(
                    title=f"{sales_col} vs {budget_col} Waterfall",
                    yaxis_title="USD",
                    xaxis_title=x_col
                )

                st.plotly_chart(fig, use_container_width=True)

            else:
                # fallback to previous chart logic
                if len(numeric_cols) >= 1 and len(categorical_cols) >= 1:
                    time_cols = [col for col in df_chart.columns if any(word in col.lower() for word in ["month","quarter","year","date"])]

                    if time_cols:
                        x_col = time_cols[0]  # Use Month/Quarter/Year as X
                        # Choose first numeric column that is not X
                        numeric_cols_filtered = [col for col in numeric_cols if col != x_col]
                        if numeric_cols_filtered:
                            y_col = numeric_cols_filtered[0]
                        else:
                            y_col = numeric_cols[0]  # fallback
                    else:
                        x_col = categorical_cols[0]
                        y_col = numeric_cols[0]
                        x_lower = x_col.lower()
                        y_lower = y_col.lower()

                    # Sort dataframe first so charts appear chronologically
                    if any(word in x_col.lower() for word in ["month", "quarter", "year", "date"]):
                        df_chart = df_chart.sort_values(by=x_col)
                        fig = px.line(df_chart, x=x_col, y=y_col, markers=True, title=f"{y_col} over {x_col}")

                    elif any(word in y_lower for word in ["percent", "share", "mix"]):
                        fig = px.pie(df_chart, names=x_col, values=y_col, hole=0.4, title=f"{y_col} by {x_col}")
                    else:
                        fig = px.bar(df_chart, x=x_col, y=y_col, title=f"{y_col} by {x_col}")

                    # Y-Axis formating
                    fig.update_yaxes(tickprefix="$", tickformat=",")
                    
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