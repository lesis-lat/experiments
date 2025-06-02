#!/usr/bin/env perl

use 5.030;
use strict;
use warnings;
use JSON;
use LWP::UserAgent;
use Data::Dumper;

sub main {
    my $userAgent = LWP::UserAgent -> new (
        agent => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)',
    );

    for (my $page = 1; $page <= 15; $page++) {
        my $request = $userAgent -> get("https://bugcrowd.com/programs.json?page[]=$page");

        print "Company, Min, Max\n";

        if ($request -> code() == 200) {
            my $data = decode_json($request -> content());
        
            foreach my $program (@{$data -> {programs}}) {
                my $name = $program -> {program_url};
                print "$name\n";
            }
        }
    }
    
    return 0;
}

exit main();