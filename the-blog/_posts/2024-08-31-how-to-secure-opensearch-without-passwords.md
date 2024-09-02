---
description: You've heard of securing node-cluster connections with certificates. Get ready for that, but for the dashboard-cluster connection.
---

# Secure OpenSearch dashboard-cluster connections with certificates

I have spent a lot of time trying to figure out how to secure communications between the dashboard and cluster of an OpenSearch instance without the use of passwords, and I finally solved it recently.

I only found [one other discussion](https://forum.opensearch.org/t/opensearch-dashboards-does-not-authenticate-to-opensearch-cluster-using-certificates-mtls/15870) of this topic in my search for other users' experiences with this. That poster's name is Nick; his problem turned out to be a misconfiguration in a tangentially related part of OpenSearch. I actually fixed my problems by copying much of his configuration.

I had a lot of difficulty debugging this, which might be a skill issue rather than an OpenSearch issue. Regardless, this post is meant to assist others looking to secure communications between the OpenSearch dashboard and cluster without the use of passwords.

Note that this is not about how to authenticate end users to the dashboard using SSL certificates (though that is also possible to configure). This is about getting the dashboard to authenticate itself to the cluster with certificates rather than username and password.

This post would more naturally fit as a documentation page in the OpenSearch project, but [the process for contributing](https://github.com/opensearch-project/documentation-website/blob/main/CONTRIBUTING.md) to the documentation website is a bit involved for my taste. Instead, I invite any maintainer or documentation writer for the OpenSearch Project to copy, modify, and distribute this work, without limitation.[^copyright]

I used a Docker instance of OpenSearch for this, but I believe the configurations should work regardless of how you're launching OpenSearch, except maybe if you're using a Windows instance.

## The error message (and lack thereof)

The error that I kept running into over and over as I tried to implement this was the following (with whitespace added for clarity):

```json
{
    "type":"log",
    "@timestamp":"...",
    "tags":["error","opensearch","data"],
    "pid":1,
    "message":"[ResponseError]: Response Error"
}
```

I wouldn't call that descriptive. To make matters worse, neither node in my cluster threw any kind of error, debug message or even trace upon authentication failures, even after I changed the log settings to maximize verbosity.

Nick also described a lack of logging from the cluster, "as if the request wasn't coming cleanly through," he said. However, he was smarter than me, and he made a `curl` request to attempt to isolate the issue further.

```sh
curl https://opensearch-cluster:9200/_plugins/_security/authinfo?pretty \
    --cacert dashboards/ca.crt \
    --cert dashboards/tls.crt \
    --key dashboards/tls.key
```

Here's what he got back:

```json
{
  "user" : "User [name=opensearch-dashboards, backend_roles=[], requestedTenant=null]",
  "user_name" : "opensearch-dashboards",
  "user_requested_tenant" : null,
  "remote_address" : "10.152.1.1:52414",
  "backend_roles" : [ ],
  "custom_attribute_names" : [ ],
  "roles" : [
    "readall_and_monitor",
    "kibana_user",
    "all_access"
  ],
  "tenants" : {
    "opensearch-dashboards" : true,
    "global_tenant" : true
  },
  "principal" : "CN=opensearch-dashboards",
  "peer_certificates" : "2",
  "sso_logout_url" : null
}
```

This indicates the request was successful, yet he did not get any logs from the cluster.

In that same thread, a major contributor to the OpenSearch forums said that he **did** get logs when he made similar requests using a minimally tweaked version of the default configuration, so I suppose it's an open matter whether the logs are sufficiently informative.

Regardless, here are the settings I was able to identify as critical to this task.

## The critical configurations

I have not included any settings for the `opensearch/config/opensearch.yml` file, but you'll have to change a few settings when you [generate certificates](https://opensearch.org/docs/latest/security/configuration/generate-certificates/) and [configure](https://opensearch.org/docs/latest/security/configuration/tls/) OpenSearch to use them.

Note that the dashboard is not considered a node of the cluster, so you don't have to add its distinguished name (DN) to `plugins.security.nodes_dn` in `opensearch.yml`.

Once you have done the other security configurations, generate a certificate for the dashboard, which it will present to the cluster at bootup. In the example here, this certificate is named `dashboard-internal-certificate.pem` and its key is `dashboard-internal-certificate-key.pem`.

Note that, unless you want to use a certificate and basic authentication together to connect the dashboard to the cluster, you can (and should) remove the `opensearch.username` and `opensearch.password` settings from `opensearch_dashboards.yml`.

{% capture code_snippet %}

```yml
opensearch:
    ssl:
        alwaysPresentCertificate: true
        certificate: /usr/share/opensearch-dashboards/config/secrets/dashboard-internal-certificate.pem
        key: /usr/share/opensearch-dashboards/config/secrets/dashboard-internal-certificate-key.pem
        
        # Optional: Enables you to specify a path to the PEM file for the certificate authority for your OpenSearch instance.
        certificateAuthorities:
            - /usr/share/opensearch-dashboards/config/secrets/root-CA.pem
            - /usr/share/opensearch-dashboards/config/secrets/intermediate-CA.pem
            
        # Optional: To disregard the validity of SSL certificates, change this setting's value to 'none'.
        verificationMode: full
```

{% endcapture %}

{% include authoring/code_file_snippet.html
    file_name = "opensearch-dashboards/config/opensearch_dashboards.yml"
    code_snippet = code_snippet
%}

One of the authentication domains you include in `opensearch-security/config.yml` must have the type `clientcert`, as shown in the following.

Beware that if you include basic authentication as an option in this file, it can cause the cluster to inappropriately authenticate a user without checking for a valid certificate, as long as they present a valid username+password combination.

{% capture code_snippet %}

```yml
config:
    dynamic:
        authc:
            # Key name can be anything:
            client_certificate_authentication:
                # Optional:
                description: "Authenticate via SSL client certificates"
                order: 1 # May vary
                http_authenticator:
                    type: clientcert
                    config:
                        # Optional. Defaults to DN if omitted:
                        username_attribute: cn
                    challenge: false
                authentication_backend:
                    type: noop
```

{% endcapture %}

{% include authoring/code_file_snippet.html
    file_name = "opensearch/config/opensearch-security/config.yml"
    code_snippet = code_snippet
%}

And finally, you need to map the dashboard user to the `kibana_server` role, which OpenSearch automatically generates.

{% capture code_snippet %}

```yml
kibana_server:
    reserved: true
    users:
        - "cn-of-the-internal-certificate"
```

{% endcapture %}

{% include authoring/code_file_snippet.html
    file_name = "opensearch/config/opensearch-security/roles_mapping.yml"
    code_snippet = code_snippet
%}

`cn-of-the-internal-certificate` should be replaced with the common name (CN) of the `dashboard-internal-certificate.pem` created earlier, or the DN of that certificate if you omitted the `username_attribute` setting from `opensearch-security/config.yml`.

## Potential pitfalls and debugging tips

One major pitfall in this whole process is certificate generation and authentication. It took me a long time to figure out that I was better off using OpenSSL to generate certificates rather than Keychain Access and the built-in Certificate Assistant for macOS. It seems there are versioning issues that I didn't care enough to investigate once I figured out I was doing that part wrong.

Using `curl` to emulate the behavior like Nick did probably would have helped me out had I figured out sooner to try that, but this has some shortcomings besides the lack of logging he and I documented.

The main one is that, as far as I can tell, the behavior of the dashboard server is not well documented. This means that if you want to emulate the dashboard's requests to the cluster by making your own `curl` requests, you'll have to do some legwork.

The main debugging method I found helpful was changing configurations bit by bit to observe changes in behavior from OpenSearch and using a local `git` repository to track these changes and make snapshots of configurations that work.

This method helped me figure out, for example, that OpenSearch does not simply run `securitadmin.sh` whenever the `.opensearch_security` index is empty or nonexistent. Rather, you have to run it yourself to make changes to the security configuration, even if you're spinning the instance up for the first time.

Lastly, use `docker compose down -v` even if the instance is not running to effectively erase the instance and start over when you spin it up again. Note that this will erase all the imported data in OpenSearch.


[^copyright]: I hereby transfer to the OpenSearch Project all my rights to this work worldwide under copyright law, including all related and neighboring rights, to the extent allowed by law.
