#!/usr/bin/env perl

use 5.030;
use strict;
use warnings;

sub main {
    my $sheet = $ARGV[0];

    if ($sheet) {
        open (my $file, '<', $sheet);

        while (<$file>) {
            chomp $_;
        
            $_ =~ s/,/./g;
            
            print $_ . "\n";
        }

        close ($file);
    }
}

exit main();