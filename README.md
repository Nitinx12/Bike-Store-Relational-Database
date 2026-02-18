# Bicycle Retail Project

![License](https://img.shields.io/badge/license-MIT-blue) ![Version](https://img.shields.io/badge/version-1.0.0-green)

## Project Overview
*The primary goal of this project is to analyze the sales data of a bicycle retail chain to generate actionable insights for business growth. The study aims to identify top-selling products, evaluate staff performance, and optimize inventory management to minimize stock-out risks and maintain efficient supply levels.*

<img width="800" height="450" alt="image" src="https://github.com/user-attachments/assets/1fb0edef-67f6-454d-8bee-06fa02341374" />


## Business Problem

Before implementing data analytics, the bicycle retail chain operated with little visibility into its business performance. The absence of structured data tracking led to several critical operational and strategic challenges:

### 1. Revenue Blindness
The company lacked insight into which brands, product categories, or individual products generated the most revenue and profit. This made strategic decision-making difficult and often resulted in suboptimal product focus.

### 2. Staff Performance Uncertainty
Management had no objective way to evaluate sales staff performance. It was unclear which employees were high performers and which required additional training or support.

### 3. Poor Customer Retention Insights
The business could not identify high-value customers — those who purchased frequently and contributed significantly to total revenue. Without this information, targeted marketing and loyalty initiatives were impossible.

### 4. Inventory Mismanagement
Inventory decisions were made without data support, leading to two major issues:
* **Dead Stock:** Slow-moving products accumulated, tying up capital.
* **Stock-Outs:** High-demand bikes frequently went out of stock, leading to lost sales.

This imbalance resulted in lost sales opportunities, increased holding costs, and reduced customer satisfaction.

---

## Our Data-Driven Solution

To resolve operational inefficiencies, I designed and implemented a **Centralized Relational Database System** using PostgreSQL. This solution transformed raw transactional data into actionable strategic insights.

### Key Technical Implementations & Insights

#### 1. Solved Revenue Blindness
I engineered complex SQL queries to aggregate sales data, revealing that company revenue is highly concentrated among a few key players. This allowed us to move from guesswork to data-backed strategy.

**Top Revenue-Generating Brands:**

| Brand Name | Total Revenue ($) | Market Position |
| :--- | :--- | :--- |
| **Trek** | **$4,602,754.35** | **Dominant Driver:** Indicates exceptionally strong market demand and brand preference. |
| **Electra** | **$1,205,320.82** | **Strong Contributor:** Suggests a stable presence in a niche segment. |
| **Surly** | **$949,507.06** | **Steady Performer:** A smaller but meaningful contributor to overall sales. |

<img width="1253" height="677" alt="image" src="https://github.com/user-attachments/assets/27e0f5f5-7cae-4f48-8e9c-66ce2a8abcac" />

**Revenue by Product Category:**

| Category | Total Revenue ($) | Customer Preference Insight |
| :--- | :--- | :--- |
| **Mountain Bikes** | **$2,715,079.53** | **#1 Best Seller:** Strong demand for off-road and adventure cycling. |
| **Road Bikes** | **$1,665,098.49** | Driven by fitness enthusiasts and long-distance riders. |
| **Cruiser Bicycles** | **$995,032.62** | Popular among casual riders for leisure and comfort. |

<img width="1189" height="790" alt="cate" src="https://github.com/user-attachments/assets/ac8d5b5b-4c4d-4293-9aab-c9eac6e219c8" />

---

#### 2. Quantified Staff Performance
Management can now objectively evaluate employees using a dynamic leaderboard system created via SQL.

* **Technical Approach:** Utilized SQL Window Functions (`DENSE_RANK`, `ROW_NUMBER`) to rank staff based on total revenue generated and order volume.
* **Outcome:** Revealed a critical retention issue regarding top talent.

**Top Performing Sales Associates:**
| Rank | Staff Name | Store Location | Revenue ($) | Status |
| :--- | :--- | :--- | :--- | :--- |
| **#1** | **Marcelene Boyer** | Baldwin Bikes | **$2,624,121** | Active |
| **#2** | **Venita Daniel** | Baldwin Bikes | **$2,591,631** | **Inactive** |
| **#3** | **Genna Serrano** | Santa Cruz Bikes | **$853,287** | Active |
| **#4** | **Kali Vargas** | Rowlett Bikes | **$463,918** | Active |

**Key Business Insight:**
* **Talent Loss:** **Venita Daniel**, the #2 performer contributing **$2.59M** in revenue, has left the company (Inactive). This represents a massive loss in sales capability and requires an immediate HR review of retention policies.
* **Store Dominance:** Staff at **Baldwin Bikes** are outperforming other branches by a factor of 3x.

---

#### 3. Optimized Inventory Management
Addressed the "Stock-Out" vs "Dead Stock" dilemma by analyzing the correlation between Order Volume and Current Stock Levels.

* **Technical Approach:** Performed `JOIN` operations between `Orders` and `Stocks` tables to calculate the **Sales-to-Stock Ratio**.
  **Inventory Health Report:**

| Product Name | Stock | Days Since Last Sale | Status | Action Required |
| :--- | :--- | :--- | :--- | :--- |
| **Trek 820 - 2016** | **55** | N/A (0 Sales) | **Dead Stock** | **Clearance Sale** |
| **Ritchey Timberwolf** | 45 | 266 Days | **Slow Moving** | Discount Bundle |
| **Surly Wednesday** | 34 | 349 Days | **Moderate** | Monitor |

**Key Insight:**
* **Dead Stock Alert:** The **Trek 820** has 55 units in stock but **zero sales**. This is "Dead Capital" that needs to be liquidated immediately to free up warehouse space and cash flow.

---

## Strategic Recommendations

1.  **HR Retention Strategy:** Investigate why **Venita Daniel** (#2 Top Seller) left. Implement retention bonuses for top-tier staff like **Marcelene Boyer**.
2.  **Inventory Liquidation:** Launch a "Clearance Sale" for the **Trek 820** and other "Dead Stock" items to recover capital.
3.  **Brand Focus:** Shift marketing budget towards **Trek and Electra**, as they drive 60%+ of the revenue.

<img width="1237" height="672" alt="image" src="https://github.com/user-attachments/assets/553d1112-7810-4272-af24-6de30b156da9" />

---

### Built With
* Python
* SQL (PostgreSQL)
* Pandas
* Jupyter Notebook
* Matplotlib & Seaborn
* Duckdb
  
---

## Project Structure

```
Bicycle Retail Project/
|
├── data/                                      # Data storage (gitignored in real projects)
|   ├── raw/                                   # Raw CSV files from the 'Dataset' folder
│   |   ├── brands.csv
│   |   ├── categories.csv
│   |   ├── customers.csv
│   |   ├── order_itens.csv
│   |   ├── orders.csv
│   |   ├── products.csv
│   |   ├── staffs.csv
│   |   ├── stocks.csv
│   |   ├── stores.csv
│   └── processed/                            # Stores processed/cleaned data if needed.
│
├── src/                                      # Source code for the project
│   ├── etl/                                  # Extract, Transform, Load scripts
│   ├── __init__.py                           # Load Dataset in PostgreSQL.py
│   │
│   └── sql/                                  # SQL scripts (from 'Advanced Data Analytics')
│   │    ├── cohort_analysis.sql
│   │    ├── monthly_sales_trend.sql
│   │    ├── rfm_segmentation.sql
│   │   
│   └── sql/                                  # There are business-related reports in the business reportfolder
│       ├── customer_report.sql
│       ├── inventory_analytics.sql
│       ├── product_reports.sql
│       ├── store_report.sql
│       ├── staff_report.sql
│       ├── summary_of_everything.sql
│
├── notebooks/                                # Jupyter Notebooks 
│   ├── eda/                                  # From 'Exploratory Data analysis (EDA)' folder
│       └── exploratory_analysis.ipynb
│
├── dashboards/                               # The Power BI folder contains SQL scripts for dimension and fact tables that create the star schema, and the dashboard has been built using these SQL scripts.
│   └── sql/ 
│   │    ├── dim_products.sql
│   │    ├── dim_customers.sql
│   │    ├── dim_staffs.sql
│   │    ├── dim_stores.sql
│   │    ├── fact_sales.sql
│   │
│   └── retail_dashboard.pbix                 # From 'Power BI Dashboard' folder
│
├── .gitignore                                # Files to ignore (e.g., venv, __pycache__, local data)
├── requirements.txt                          # Python dependencies (pandas, sqlalchemy, psycopg2)
├── LICENSE
└── README.md                                 # Project Overview
```
---
## ⚙️ Installation & Usage
To replicate this analysis, follow these steps:

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/Nitinx12/Bike-Store-Relational-Database/tree/main]
    ```
2.  **Set Up PostgreSQL Database:**
    * Ensure you have PostgreSQL installed.    
 * Create a new database (e.g., `Bicycle_database`).
    * Update the connection string in the `Load_Data_in_postgreSQL.py` file with your database credentials.
3.  **Load Data:**
    * Place the 9 `.csv` files (`customers`, `products.csv`, etc.) in the `data/` directory.
    * Run the Python script to load the data into your PostgreSQL database:
        ```bash
       Load_Data_in_postgreSQL.py
        ```
4.  **Install dependencies**
    Create a `requirements.txt` file with the following content:
    ```
    pandas
    sqlalchemy
    psycopg2-binary
    matplotlib
    seaborn
    jupyter
    duckdb
    ```
    Then, run the installation command:
    ```bash
    pip install -r requirements.txt
    ```
5.  **Run Analysis:**
    * **For SQL Analysis:** Execute the queries in `product_report.sql` using a SQL client like DBeaver, pgadmin4 or `psql`.
```sql
WITH Sales_base AS(
	SELECT
		OI.product_id,
		O.order_id,
		O.customer_id,
		O.store_id,
		O.order_date,
		C.state,
		S.store_name,
		OI.quantity,
		OI.list_price,
		OI.discount,
		OI.quantity * OI.list_price * (1 - OI.discount) AS revenue,
		OI.quantity * OI.list_price * OI.discount AS discount_amount
	FROM order_items AS OI
	INNER JOIN orders AS O ON
	OI.order_id = O.order_id
	INNER JOIN customers AS C ON
	C.customer_id = O.customer_id
	INNER JOIN stores AS S ON
	S.store_id = O.store_id
),
Metrics AS(
	SELECT
		product_id,
		SUM(quantity) AS total_units_sold,
		SUM(revenue) AS total_revenue,
		COUNT(DISTINCT order_id) AS total_orders,
		COUNT(DISTINCT customer_id) AS unique_customers,
		SUM(discount_amount) AS total_discount,
		MIN(order_date) AS first_sale_date,
		MAX(order_date) AS last_sale_date
	FROM Sales_base
	GROUP BY
		product_id
),
Inventory_metrics AS(
	SELECT
		product_id,
		SUM(quantity) AS inventory_level
	FROM stocks
	GROUP BY
		product_id
),
Top_state AS(
	SELECT
		product_id,
		state,
		ROW_NUMBER()
			OVER(PARTITION BY product_id
			ORDER BY SUM(revenue) DESC) AS rnk
	FROM Sales_base
	GROUP BY
		product_id,
		state
),
Top_store AS(
	SELECT
		product_id,
		store_name,
		ROW_NUMBER()
			OVER(PARTITION BY product_id
			ORDER BY SUM(revenue) DESC) AS rnk
	FROM Sales_base
	GROUP BY
		product_id,
		store_name
),
dataset_date AS(
	SELECT 
		MAX(order_date) AS last_dataset_date
	FROM orders
),
product_segmentation AS(
	SELECT
		product_id,
		total_revenue,
		revenue_segment,
		AVG(total_revenue) OVER(PARTITION BY category_id) AS avg_category_revenue,
		CASE
			WHEN total_revenue > AVG(total_revenue) OVER(PARTITION BY category_id)
			THEN 'Above average'
			ELSE 'Below average'
		END AS performance_stats
	FROM(SELECT
			P.product_id,
			P.category_id,
			SUM(OI.total_value) AS total_revenue,
			CASE
				WHEN SUM(OI.total_value) >= 15000 THEN 'High Revenue'
				WHEN SUM(OI.total_value) BETWEEN 3000 AND 14999 THEN 'Medium Revenue'
				ELSE 'Low Revenue'
			END AS revenue_segment
		FROM products AS P
		INNER JOIN order_items AS OI ON
		P.product_id = OI.product_id
		GROUP BY
			P.product_id,
			P.category_id) AS X
)
SELECT
	P.product_name,
	B.brand_name,
	C.category_name,
	P.list_price,
	DENSE_RANK()
		OVER(PARTITION BY P.category_id
		ORDER BY COALESCE(M.total_units_sold,0) DESC) AS category_rank,
	ROUND(COALESCE(M.total_units_sold,0),2) AS total_units_sold,
	ROUND(COALESCE(M.total_revenue,0),2) AS total_revenue,
	COALESCE(M.total_orders,0) AS total_orders,
	COALESCE(M.unique_customers,0) AS unique_customers,
	CASE
		WHEN M.total_units_sold > 0
		THEN ROUND(M.total_revenue / M.total_units_sold,2)
		ELSE NULL
	END AS avg_selling_price,
	ROUND(COALESCE(M.total_discount,0),2) AS total_discount,
	M.first_sale_date,
	M.last_sale_date,
	GD.last_dataset_date - M.last_sale_date AS days_since_last_sale,
	TS.state AS top_state,
	TSS.store_name AS top_store,
	COALESCE(IM.inventory_level,0) AS inventory_level,
	PM.revenue_segment,
	ROUND(PM.avg_category_revenue,2) AS avg_category_revenue,
	PM.performance_stats,
	CASE
		WHEN M.last_sale_date IS NULL
		THEN 'Never_sold'
		WHEN GD.last_dataset_date - M.last_sale_date <= 365
		THEN 'Active'
		WHEN GD.last_dataset_date - M.last_sale_date <= 1095
		THEN 'Slow Moving'
		ELSE 'Obsolete'
	END AS lifecycle_status
FROM products AS P
LEFT JOIN brands AS B ON
B.brand_id = P.brand_id
LEFT JOIN categories AS C ON
C.category_id = P.category_id
LEFT JOIN Metrics AS M ON
M.product_id = P.product_id
LEFT JOIN Inventory_metrics AS IM ON
P.product_id = IM.product_id
LEFT JOIN Top_state AS TS ON
TS.product_id = P.product_id AND TS.rnk = 1
LEFT JOIN Top_store AS TSS ON
TSS.product_id = P.product_id AND TSS.rnk = 1
LEFT JOIN product_segmentation AS PM ON
PM.product_id = P.product_id
CROSS JOIN dataset_date AS GD;
```
---

## License

Distributed under the MIT License. See `LICENSE` for more information.

## Contact Information

* **LinkedIn:** [https://www.linkedin.com/in/nitin-k-220651351/](https://www.linkedin.com/in/nitin-k-220651351/)
* **GitHub:** [https://github.com/Nitinx12](https://github.com/Nitinx12)
* **Email:** Nitin321x@gmail.com

---

