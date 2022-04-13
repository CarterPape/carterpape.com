---
categories:
    - the-blog
    - april-2022-photo-dump
layout: "browsing/card-list"
title: "Sights of the past nine months"
description: "Instagram is stupid. Here is what I've seen recently, on my very own website."

image:
    path: "assets/posts/2022-04-12-photo-dump/2022-04-12-05-snowshoe/006-lorax.jpeg"
    use_xmp: true

seo:
    type: Blog
regenerate: true
---

{%- assign photo_dump = site.categories["april-2022-photo-dump"] -%}

{{ page.description }}

{% for each_post in photo_dump reversed %}
    {%- include post/preview.html the_post=each_post -%}
{% endfor %}
