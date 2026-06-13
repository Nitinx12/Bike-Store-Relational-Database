# Data Catalog: Retail Store Schema

## Overview

This schema represents a retail business with multiple stores, staff, products, customers, and orders. It is organized into reference (lookup) tables, operational tables, and transactional/junction tables. Every table includes an updated at column except order items, which is used for incremental loading from the source system.

## Entity Relationship Summary

The schema is built around the orders table as the central transaction record. Each order is placed by a customer, handled by a staff member, and fulfilled from a store. An order contains one or more order items, each referencing a product. Products belong to a brand and a category. Stores hold stock levels for products. Staff belong to a store and may report to a manager (another staff member).

## Table Details

### brands

Reference table for product brands.

| column | type | constraint | description |
|---|---|---|---|
| brand id | bigint | primary key | unique identifier for the brand |
| brand name | text | | name of the brand |
| updated at | timestamp | default current timestamp | last update time |

Referenced by: products (brand id)

### categories

Reference table for product categories.

| column | type | constraint | description |
|---|---|---|---|
| category id | bigint | primary key | unique identifier for the category |
| category name | text | | name of the category |
| updated at | timestamp | default current timestamp | last update time |

Referenced by: products (category id)

### customers

Customer master data.

| column | type | constraint | description |
|---|---|---|---|
| customer id | bigint | primary key | unique identifier for the customer |
| first name | text | | customer first name |
| last name | text | | customer last name |
| phone | text | | contact phone number |
| email | text | | contact email |
| street | text | | street address |
| city | text | | city |
| state | text | | state |
| zip code | bigint | | postal code |
| updated at | timestamp | default current timestamp | last update time |

Referenced by: orders (customer id)

### stores

Store master data.

| column | type | constraint | description |
|---|---|---|---|
| store id | bigint | primary key | unique identifier for the store |
| store name | text | | name of the store |
| phone | text | | contact phone number |
| email | text | | contact email |
| street | text | | street address |
| city | text | | city |
| state | text | | state |
| zip code | bigint | | postal code |
| updated at | timestamp | default current timestamp | last update time |

Referenced by: orders (store id), staffs (store id), stocks (store id)

### staffs

Employee master data, with a self referencing manager relationship.

| column | type | constraint | description |
|---|---|---|---|
| staff id | bigint | primary key | unique identifier for the staff member |
| first name | text | | staff first name |
| last name | text | | staff last name |
| email | text | | contact email |
| phone | text | | contact phone number |
| active | bigint | | whether the staff member is active |
| store id | bigint | foreign key to stores | store where the staff member works |
| manager id | bigint | foreign key to staffs | the staff member's manager |
| updated at | timestamp | default current timestamp | last update time |

References: stores (store id), staffs (manager id, self reference)
Referenced by: orders (staff id), staffs (manager id)

### products

Product master data.

| column | type | constraint | description |
|---|---|---|---|
| product id | bigint | primary key | unique identifier for the product |
| product name | text | | name of the product |
| brand id | bigint | foreign key to brands | brand of the product |
| category id | bigint | foreign key to categories | category of the product |
| model year | bigint | | model year |
| list price | numeric(10,2) | | standard list price |
| updated at | timestamp | default current timestamp | last update time |

References: brands (brand id), categories (category id)
Referenced by: order items (product id), stocks (product id)

### orders

Order header data. Central table of the schema.

| column | type | constraint | description |
|---|---|---|---|
| order id | bigint | primary key | unique identifier for the order |
| customer id | bigint | foreign key to customers | customer who placed the order |
| order status | text | | current status of the order |
| order date | date | | date the order was placed |
| required date | date | | date the order is required by |
| shipped date | date | | date the order was shipped |
| store id | bigint | foreign key to stores | store fulfilling the order |
| staff id | bigint | foreign key to staffs | staff member handling the order |
| updated at | timestamp | default current timestamp | last update time |

References: customers (customer id), stores (store id), staffs (staff id)
Referenced by: order items (order id)

### order_items

Order line items. Junction table between orders and products, with a composite primary key.

| column | type | constraint | description |
|---|---|---|---|
| order id | bigint | primary key (composite), foreign key to orders | order this line item belongs to |
| item id | bigint | primary key (composite) | line number within the order |
| product id | bigint | foreign key to products | product ordered |
| quantity | bigint | | quantity ordered |
| list price | numeric | | price per unit at time of order |
| discount | numeric | | discount applied |
| total value | numeric(12,2) | generated, stored | computed as quantity times list price times (1 minus discount) |
| updated at | timestamp | default current timestamp | last update time |

References: orders (order id), products (product id)

Note: this is the only table without a single column primary key, and it has a generated, stored computed column (total value), which makes it an exception to the otherwise uniform incremental loading pattern, since the generated column cannot be inserted directly and must be excluded from insert and update column lists.

### stocks

Inventory levels per store and product. Junction table between stores and products, with a composite primary key.

| column | type | constraint | description |
|---|---|---|---|
| store id | bigint | primary key (composite), foreign key to stores | store holding the stock |
| product id | bigint | primary key (composite), foreign key to products | product being stocked |
| quantity | bigint | | quantity on hand |
| updated at | timestamp | default current timestamp | last update time |

References: stores (store id), products (product id)

## Relationship Map

The diagram above shows the full set of relationships. Summarized as a list:

- customers to orders: one customer can place many orders
- staffs to orders: one staff member can handle many orders
- stores to orders: one store can fulfill many orders
- orders to order items: one order contains many order items
- products to order items: one product can appear in many order items
- products to brands: many products belong to one brand
- products to categories: many products belong to one category
- stores to stocks: one store holds stock for many products
- products to stocks: one product can be stocked in many stores
- staffs to stores: many staff members work at one store
- staffs to staffs: a staff member can manage other staff members (self referencing hierarchy)

## Notes for Incremental Loading

All tables except order items have a single column primary key matching the pattern table name singular plus id, which aligns with the primary key auto detection logic used by the mongo to postgres ETL script (exact match on collection name plus id, or first column ending in id).

The order items table has a composite primary key (order id, item id) and a generated column (total value). Both of these characteristics fall outside the assumptions of the ETL script described in incremental loading.md, since that script assumes a single column primary key and creates all columns as plain text, which would conflict with a generated, stored numeric column. If order items needs to be loaded by that pipeline, it would require either a dedicated handling path or a synthetic single column key (for example a concatenation of order id and item id) and exclusion of the total value column from the insert and update statements.

All other tables fit the standard pattern: single column primary key ending in id, an updated at column for incremental comparison, and straightforward upsert behavior on conflict.