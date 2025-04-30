#!/usr/bin/env perl

use 5.030;
use strict;
use warnings;
use Mojo::UserAgent;

sub fetch_programs_page {
    my ($userAgent, $page) = @_;

    my $url = "https://api.yeswehack.com/programs?page=$page";

    my $response = $userAgent->get($url => {
        'Accept' => 'application/json',
        'Content-Type' => 'application/json'
    }) -> result();

    unless ($response -> is_success) {
        die "Request failed (page $page): " . $response -> message . "\n" . ($response->body // '');
    }

    return $response->json;
}

sub print_programs {
    my ($programs) = @_;

    foreach my $program (@$programs) {
        my $name = $program -> {title};
        my $min  = $program -> {bounty_reward_min};
        my $max  = $program -> {bounty_reward_max};

        next if $min == 0 && $max == 0;

        say "$name, $min, $max";
    }
}

sub main {
    my $userAgent = Mojo::UserAgent->new;
    $userAgent -> insecure(1);
    $userAgent -> transactor -> name('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) Gecko/20100101 Firefox/137.0');

    say "Company, Min, Max";

    my $current_page = 1;
    my $total_pages = 1;

    while ($current_page <= $total_pages) {
        my $data = fetch_programs_page($userAgent, $current_page);
        
        $total_pages = $data -> {pagination} -> {nb_pages};
        
        print_programs($data -> {items});
        
        $current_page++;
    }

    return 0;
}

exit main();
