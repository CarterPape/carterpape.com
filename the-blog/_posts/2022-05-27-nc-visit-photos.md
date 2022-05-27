---
image:
    path: assets/posts/2022-05-27-nc-visit-photos/20220518_0005.jpeg
    hide_at_top_of_page: true
    use_xmp: true
---

# North Carolina and Hyco Lake

I like having a remote job because it means I can go see my family.

{% for each_file in site.static_files -%}
    {%- if each_file.path
        contains "/assets/posts/2022-05-27-nc-visit-photos/"
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
