use strict;
use warnings;
use Mojo::UserAgent;
use Mojo::JSON qw(decode_json);

my $token = '';
my $url = 'https://api.intigriti.com/external/researcher/programs';

my $ua = Mojo::UserAgent->new;

my $res = $ua->get($url => {
    Authorization => "Bearer $token",
    Accept        => 'application/json'
})->result;

if ($res->is_success) {
    my $programs = $res->json;

    foreach my $program (@$programs) {
        print "Nome: $program->{name}\n";
        print "Slug: $program->{slug}\n" if exists $program->{slug};
        print "Status: $program->{status}\n";
        print "--------------------------\n";
    }
} else {
    die "Erro: " . $res->code . " - " . $res->message . "\n";
}
