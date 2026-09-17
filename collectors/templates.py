"""Downloadable import examples."""

BOOKS_CSV_TEMPLATE = """source,source_identifier,asin,title,subtitle,author,publisher,publication_date,format,price,page_count,rating,review_count,best_seller_rank,category,product_reference,description,notes
manual,BOOK-001,,Example Practical Guide,,Sample Author,Independent,2025-01-15,Paperback,16.99,180,4.3,125,45000,Example category,,Original example row,
"""

REVIEWS_CSV_TEMPLATE = """book_identifier,source,source_review_identifier,rating,title,body,review_date,verified_purchase,helpful_votes
BOOK-001,manual,REVIEW-001,3,Useful but incomplete,The overview was clear but I wanted more worked examples.,2026-08-01,true,2
"""

BOOKS_JSON_TEMPLATE = """{
  "books": [
    {
      "source": "manual",
      "source_identifier": "BOOK-001",
      "title": "Example Practical Guide",
      "author": "Sample Author",
      "format": "Paperback",
      "price": 16.99,
      "rating": 4.3,
      "review_count": 125
    }
  ]
}
"""

REVIEWS_JSON_TEMPLATE = """{
  "reviews": [
    {
      "book_identifier": "BOOK-001",
      "source": "manual",
      "source_review_identifier": "REVIEW-001",
      "rating": 3,
      "title": "Useful but incomplete",
      "body": "The overview was clear but I wanted more worked examples.",
      "review_date": "2026-08-01"
    }
  ]
}
"""

