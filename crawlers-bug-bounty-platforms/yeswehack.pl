#!/usr/bin/env perl

use 5.030;
use strict;
use warnings;
use Mojo::UserAgent;

binmode STDOUT, ':encoding(UTF-8)';

sub fetch_programs_page {
    my ($userAgent, $page) = @_;

    my $url = "https://api.yeswehack.com/programs?page=$page";

    my $response = $userAgent->get($url => {
        'Accept' => 'application/json',
        'Content-Type' => 'application/json'
    })->result();

    unless ($response->is_success) {
        die "Request failed (page $page): " . $response->message . "\n" . ($response->body // '');
    }

    return $response->json;
}

sub main {
    my $userAgent = Mojo::UserAgent->new;
    $userAgent->insecure(1);
    $userAgent->transactor->name('Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:137.0) Gecko/20100101 Firefox/137.0');

    my @all_programs;
    my $current_page = 1;
    my $total_pages = 1;

    while ($current_page <= $total_pages) {
        my $data = fetch_programs_page($userAgent, $current_page);
        $total_pages = $data->{pagination}->{nb_pages};

        foreach my $program (@{$data->{items}}) {
            my $min = $program->{bounty_reward_min} // 0;
            my $max = $program->{bounty_reward_max} // 0;
            if (!($min == 0 && $max == 0)) {
                push @all_programs, $program;
            }
        }
        $current_page++;
    }

    my $max_name_length = 0;
    foreach my $program (@all_programs) {
        my $length = length($program->{title});
        $max_name_length = $length if $length > $max_name_length;
    }

    printf "%-*s %10s %10s\n", $max_name_length, "Company", "Min", "Max";

    foreach my $program (@all_programs) {
        my $name = $program->{title};
        my $min  = $program->{bounty_reward_min} // 0;
        my $max  = $program->{bounty_reward_max} // 0;
        printf "%-*s %10d %10d\n", $max_name_length, $name, $min, $max;
    }

    return 0;
}

exit main();
