# 🔖 Content-addressed cache-busting for site-wide assets.
#
# Registers a `cache_bust` Liquid filter that turns a built-asset path into its
# relative URL with a `?v=<digest>` query string, where the digest is a hash of
# the asset's *source* bytes. The version therefore changes only when the asset
# actually changes — unlike the old build-timestamp approach, which rewrote the
# `?v=` on every page on every build and made every deploy re-upload ~50 files.
#
# We hash source rather than compiled output because the only compiled asset is
# main.css (from main.scss + the _scss/ tree), and Liquid renders head.html
# before that SCSS is written to _site/ — so the compiled bytes aren't available
# at render time. Hashing the SCSS source tree busts the cache on every real
# style change, which is the whole point. The static CSS/JS are hashed directly.

require "digest"

module CacheBuster
    # Reuse Jekyll's own relative_url (reads @context.registers[:site]) instead of
    # reimplementing baseurl handling.
    include Jekyll::Filters::URLFilters

    # 📁 Built-asset path → glob(s) of the source files whose bytes define its version.
    SOURCE_GLOBS = {
        "assets/style/main.css" => ["assets/style/main.scss", "_scss/**/*.scss"],
        "assets/style/pygment_trac.css" => ["assets/style/pygment_trac.css"],
        "assets/js/main.js" => ["assets/js/main.js"],
    }.freeze

    def cache_bust(asset_path)
        site = @context.registers[:site]
        # fetch (not []) so an unmapped asset fails the build loudly, matching the
        # site's strict-everything posture (Liquid strict_* + error_mode: strict).
        globs = SOURCE_GLOBS.fetch(asset_path)
        files = globs.flat_map { |glob| Dir[File.join(site.source, glob)] }.uniq.sort
        raise "cache_bust: no source files found for #{asset_path}" if files.empty?

        digest = Digest::SHA256.new
        files.each { |file| digest.update(File.binread(file)) }
        "#{relative_url(asset_path)}?v=#{digest.hexdigest[0, 12]}"
    end
end

Liquid::Template.register_filter(CacheBuster)
