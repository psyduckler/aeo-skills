# Schema Templates for AEO

JSON-LD templates optimized for AI citation. Replace placeholder values with actual page data.

---

## Article

Best for: blog posts, guides, analysis, news articles, reviews.

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "Your Article Title (max 110 chars)",
  "description": "A concise 150-160 character description of the article content.",
  "image": "https://example.com/article-hero.jpg",
  "author": {
    "@type": "Person",
    "name": "Author Name",
    "url": "https://example.com/about/author-name",
    "sameAs": [
      "https://twitter.com/authorhandle",
      "https://linkedin.com/in/authorname"
    ],
    "jobTitle": "Job Title / Credentials"
  },
  "publisher": {
    "@type": "Organization",
    "name": "Publisher Name",
    "logo": {
      "@type": "ImageObject",
      "url": "https://example.com/logo.png"
    }
  },
  "datePublished": "2025-01-15T08:00:00+00:00",
  "dateModified": "2025-03-10T14:30:00+00:00",
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "https://example.com/article-slug"
  },
  "about": {
    "@type": "Thing",
    "name": "Main Topic"
  },
  "keywords": ["keyword1", "keyword2", "keyword3"],
  "wordCount": 2500,
  "inLanguage": "en"
}
```

**AEO-critical fields:** `headline`, `author` (with credentials), `dateModified`, `description`.

---

## FAQPage

Best for: pages with Q&A content, FAQ sections within articles, comparison pages.

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "What is the exact question?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "The direct, concise answer. Keep to 1-3 sentences for AI extractability. Can include <a href='https://example.com'>links</a> if helpful."
      }
    },
    {
      "@type": "Question",
      "name": "How do you do X?",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "Step-by-step or direct answer. Be specific — include numbers, names, and actionable details."
      }
    }
  ]
}
```

**AEO-critical fields:** `name` (question text), `text` (direct answer — first 1-2 sentences matter most).

**Tips:**
- Limit to 10 Q&As per page (Google may ignore excess)
- Use exact question phrasing from the page headings
- Answer text should be self-contained (makes sense without reading the article)
- Best ROI schema type for AEO — directly provides extractable Q&A pairs

---

## HowTo

Best for: tutorials, step-by-step guides, recipes, DIY instructions.

```json
{
  "@context": "https://schema.org",
  "@type": "HowTo",
  "name": "How to [Do the Thing]",
  "description": "Brief overview of what this guide teaches.",
  "totalTime": "PT30M",
  "estimatedCost": {
    "@type": "MonetaryAmount",
    "currency": "USD",
    "value": "50"
  },
  "supply": [
    {
      "@type": "HowToSupply",
      "name": "Required item/material"
    }
  ],
  "tool": [
    {
      "@type": "HowToTool",
      "name": "Required tool/software"
    }
  ],
  "step": [
    {
      "@type": "HowToStep",
      "name": "Step 1 Title",
      "text": "Detailed instructions for this step. Be specific and actionable.",
      "url": "https://example.com/guide#step1",
      "image": "https://example.com/step1.jpg"
    },
    {
      "@type": "HowToStep",
      "name": "Step 2 Title",
      "text": "Next step instructions.",
      "url": "https://example.com/guide#step2"
    }
  ]
}
```

**AEO-critical fields:** `step` entries with clear `name` and `text`, `totalTime`.

---

## Product

Best for: product pages, software tools, SaaS pricing pages.

```json
{
  "@context": "https://schema.org",
  "@type": "Product",
  "name": "Product Name",
  "description": "Product description — what it does and who it's for.",
  "image": "https://example.com/product.jpg",
  "brand": {
    "@type": "Brand",
    "name": "Brand Name"
  },
  "offers": {
    "@type": "AggregateOffer",
    "lowPrice": "29",
    "highPrice": "199",
    "priceCurrency": "USD",
    "offerCount": 3,
    "availability": "https://schema.org/InStock"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.5",
    "reviewCount": "1200",
    "bestRating": "5"
  },
  "review": [
    {
      "@type": "Review",
      "author": {
        "@type": "Person",
        "name": "Reviewer Name"
      },
      "reviewRating": {
        "@type": "Rating",
        "ratingValue": "5"
      },
      "reviewBody": "Short review text."
    }
  ]
}
```

**AEO-critical fields:** `aggregateRating`, `offers` (pricing), `description`.

---

## LocalBusiness

Best for: restaurants, shops, service providers, offices with physical locations.

```json
{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Business Name",
  "description": "What the business does, who it serves.",
  "image": "https://example.com/storefront.jpg",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "123 Main St",
    "addressLocality": "City",
    "addressRegion": "ST",
    "postalCode": "12345",
    "addressCountry": "US"
  },
  "geo": {
    "@type": "GeoCoordinates",
    "latitude": 40.7128,
    "longitude": -74.0060
  },
  "telephone": "+1-555-123-4567",
  "url": "https://example.com",
  "priceRange": "$$",
  "openingHoursSpecification": [
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
      "opens": "09:00",
      "closes": "18:00"
    },
    {
      "@type": "OpeningHoursSpecification",
      "dayOfWeek": ["Saturday"],
      "opens": "10:00",
      "closes": "14:00"
    }
  ],
  "sameAs": [
    "https://facebook.com/businessname",
    "https://instagram.com/businessname"
  ]
}
```

**AEO-critical fields:** `address`, `openingHoursSpecification`, `geo`, `telephone`.

---

## BreadcrumbList

Best for: every page. Helps AI understand site structure and topic hierarchy.

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "https://example.com"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": "Blog",
      "item": "https://example.com/blog"
    },
    {
      "@type": "ListItem",
      "position": 3,
      "name": "Article Title",
      "item": "https://example.com/blog/article-slug"
    }
  ]
}
```

**Tips:** Always include BreadcrumbList alongside other schema types. It's low effort and helps AI models understand where a page sits in the site hierarchy.

---

## Combining Multiple Schema Types

Pages often benefit from multiple schema blocks. Wrap them in a `@graph`:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Article",
      "headline": "...",
      "...": "..."
    },
    {
      "@type": "FAQPage",
      "mainEntity": ["..."]
    },
    {
      "@type": "BreadcrumbList",
      "itemListElement": ["..."]
    }
  ]
}
```

Or use separate `<script type="application/ld+json">` blocks — both approaches are valid.
