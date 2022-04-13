---
categories:
    - the-blog
    - april-2022-photo-dump
layout: "browsing/card-list"
title: "Sights of the past nine months"
description: "What I've seen recently, on my very own website."

image:
    path: "assets/posts/2022-04-12-photo-dump/2022-04-12-05-snowshoe/006-lorax.jpeg"
    use_xmp: true

seo:
    type: Blog
regenerate: true
---

{%- assign photo_dump = site.categories["april-2022-photo-dump"] -%}

I took most of these photos with my iPhone. It's a pretty good camera, but I want a real camera to take better photos. I might even make them easier and nicer to view online once I do!

{% for each_post in photo_dump reversed %}
    {%- include post/preview.html the_post=each_post -%}
{% endfor %}
