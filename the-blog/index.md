---
categories:
    - the-blog
layout: "browsing/card-list"
title: "the blog"
description: "a public repository of my personally and professionally relevant musings, updates, ideas, and more"

redirect_from:
    - /blog/
seo:
    type: Blog
regenerate: true
---

{% assign blog_feed = site.categories["the-blog"] %}

{% for each_post in blog_feed %}
    {%- unless each_post.hide_from_blog_index -%}
        {%- include post/preview.html the_post=each_post -%}
    {%- endunless -%}
{% endfor %}
