use strict;
use warnings;
use Test::More tests => 3;
use FindBin;
use lib "$FindBin::Bin/../lib";
use FxReport::Rates;

my $today = { EURUSD => { close => 1.1000, high => 1.11, low => 1.09, avg => 1.1 } };
my $prev  = { EURUSD => { close => 1.0000 } };
my $rows  = FxReport::Rates::moves($today, $prev);
is(scalar @$rows, 1, 'one pair');
cmp_ok(abs($rows->[0]{chg_pct} - 10), '<', 1e-9, 'ten percent move');
ok(!defined FxReport::Rates::moves($today, undef)->[0]{chg_pct}, 'no previous day, no change');
