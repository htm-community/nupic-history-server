# NuPIC History Server

> Runs NuPIC behind a web server, exposing internals. For HTM School.

This is a work in progress. I'm building it to have a consistent HTTP server protocol that will run HTM components, save their states over time, and expose the internal state to web clients.

This relies very heavily on Redis as an in-memory cache (instead of using web sessions). The nice thing is that the history can be maintained in Redis and replayed after the web server has been restarted.
