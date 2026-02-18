# Bike-Store-Relational-Database

## Project Overview
*The primary goal of this project is to analyze the sales data of a bicycle retail chain to generate actionable insights for business growth. The study aims to identify top-selling products, evaluate staff performance, and optimize inventory management to minimize stock-out risks and maintain efficient supply levels.*

<img width="800" height="450" alt="image" src="https://github.com/user-attachments/assets/1fb0edef-67f6-454d-8bee-06fa02341374" />

# Bicycle Retail Data Analytics Project

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

**Revenue by Product Category:**

| Category | Total Revenue ($) | Customer Preference Insight |
| :--- | :--- | :--- |
| **Mountain Bikes** | **$2,715,079.53** | **#1 Best Seller:** Strong demand for off-road and adventure cycling. |
| **Road Bikes** | **$1,665,098.49** | Driven by fitness enthusiasts and long-distance riders. |
| **Cruiser Bicycles** | **$995,032.62** | Popular among casual riders for leisure and comfort. |

---

#### 2. Quantified Staff Performance
Management can now objectively evaluate employees using a dynamic leaderboard system created via SQL.

* **Technical Approach:** Utilized SQL Window Functions (`DENSE_RANK`, `ROW_NUMBER`) to rank staff based on total revenue generated and order volume.
* **Outcome:** Identified top-performing sales associates in each store, enabling a reward system, while pinpointing underperformers for targeted training programs.

---

#### 3. Optimized Inventory Management
Addressed the "Stock-Out" vs "Dead Stock" dilemma by analyzing the correlation between Order Volume and Current Stock Levels.

* **Technical Approach:** Performed `JOIN` operations between `Orders` and `Stocks` tables to calculate the **Sales-to-Stock Ratio**.
* **Outcome:** Flagged high-demand models (like Trek Mountain Bikes) for immediate restocking and identified slow-moving inventory for discount clearance sales.

---

#### 4. Customer Segmentation & Retention
Transitioned from mass marketing to targeted engagement by identifying high-value customer clusters.

* **Technical Approach:** Analyzed customer location data (City/State) and Purchase Frequency using aggregate functions.
* **Outcome:** Discovered that customers in **NY and CA** generate the highest average order value, allowing for location-specific marketing campaigns.

---

## Strategic Recommendations

Based on the data analysis, the following actions are recommended to maximize growth:

1.  **Prioritize the "Power Trio":** Since **Trek, Electra, and Surly** drive the majority of revenue, marketing budgets should be allocated heavily towards these brands to maximize ROI.
2.  **Inventory Rebalancing:** Increase stock levels for **Mountain Bikes** before the peak season to prevent lost sales due to stock-outs.
3.  **Staff Training:** Pair low-performing staff with top-tier sales associates (identified in the report) for mentorship programs.
4.  **Targeted Promotions:** Launch a "Leisure Rider" campaign specifically for **Cruiser Bicycles** to boost sales in the casual segment.

---









