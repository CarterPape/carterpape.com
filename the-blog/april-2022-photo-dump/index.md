---
categories:
    - the-blog
    - april-2022-photo-dump
layout: "browsing/card-list"
title: "Sights of the past nine months"
description: "Instagram is stupid. Here is what I've seen recently, on my very own website."

seo:
    type: Blog
regenerate: true
---

{%- assign photo_dump = site.categories["april-2022-photo-dump"] -%}

{{ page.description }}

*Note: While some of the photos in this photo dump have a Creative Commons license, others are not licensed for reuse. The terms for each photo are contained in the caption below it.*

{% for each_post in photo_dump reversed %}
    {%- include post/preview.html the_post=each_post -%}
{% endfor %}
