---
image:
    path: assets/posts/2022-04-12-photo-dump/2022-04-12-08-san-francisco/015-Golden-Gate.jpeg
    hide_at_top_of_page: true
    use_xmp: true
---

# San Francisco

I went to visit Josh in San Francisco. I also surprised Chatham, and then Mitch surprised me by showing up.

{% for each_file in site.static_files -%}
    {%- if each_file.path
        contains "/assets/posts/2022-04-12-photo-dump/2022-04-12-08-san-francisco/"
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
