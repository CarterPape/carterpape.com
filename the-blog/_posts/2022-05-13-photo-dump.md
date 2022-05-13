---
image:
    path: assets/posts/2022-05-13-photo-dump/2022-05-13-02-silver-falls/20220507-0011.jpeg
    hide_at_top_of_page: true
    use_xmp: true
---

# Portland, Seattle, and Silver Falls State Park

I went on a few more adventures in the last month.

{% for each_file in site.static_files -%}
    {%- if each_file.path
        contains "/assets/posts/2022-05-13-photo-dump/"
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
