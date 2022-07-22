---
image:
    path: assets/posts/2022-07-21-photo-dump/20220716_0009.jpeg
    hide_at_top_of_page: true
    use_xmp: true

hide_word_count: true
---

# Nampa, Corvallis, Klamath

In June, I saw my granny, and in July, I saw southern Oregon.

{% for each_file in site.static_files -%}
    {%- if each_file.path
        contains "/assets/posts/2022-07-21-photo-dump/"
    -%}
        {%- if each_file.extname == '.jpg'
            or each_file.extname == '.jpeg'
            or each_file.extname == '.JPG'
            or each_file.extname == '.JPEG'
        -%}
            {%- include authoring/image.html
                image_path = each_file.path
                link = each_file.path
                is_decorative = true
                use_xmp = true
            -%}
        {%- endif -%}
    {%- endif -%}
{%- endfor -%}
