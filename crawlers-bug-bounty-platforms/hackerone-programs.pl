#!/usr/bin/env perl

use strict;
use warnings;
use JSON;
use MIME::Base64;
use Mojo::UserAgent;

my $token = "";
my $useragent = Mojo::UserAgent->new();

for (my $i = 0; $i <= 100; $i++) {
    my $api_url = "https://api.hackerone.com/v1/hackers/programs?page[size]=100&page[number]=$i";

    my $response = $useragent->get($api_url => {
        "Content-Type"  => "application/json",
        "Authorization" => "Basic " . encode_base64("$token:", "")
    });

    my $result = $response->result;

    if ($result->is_success) {
        my $data = decode_json($result->body);

        my $count = 0;
        for my $program (@{$data->{"data"}}) {
            print $program->{"attributes"}->{"handle"}, "\n";
            $count++;
        }

        last if $count == 0;
    } else {
        warn "Failed request on page $i: " . $result->message . "\n";
        last;
    }
}
