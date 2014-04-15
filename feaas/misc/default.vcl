director app dns {
	{
		.backend = {
			.host = "%(app_host)s";
			.port = "80";
		}
	}
	.ttl = 5m;

}

sub vcl_recv {
	set req.http.X-Host = req.http.host;
	set req.http.Host = "%(app_host)s";

	if(req.url ~ "/_varnish_healthcheck") {
		error 200 "WORKING";
		set req.http.Connection = "close";
	}
}

sub vcl_fetch {
	if(beresp.http.X-Esi) {
		set beresp.do_esi = true;
		unset beresp.http.X-Esi;
	}
}
