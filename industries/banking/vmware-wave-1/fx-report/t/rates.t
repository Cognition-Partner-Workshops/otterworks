use strict;
use warnings;
use Test::More;
use File::Temp qw(tempdir);
use FindBin;
use lib "$FindBin::Bin/../lib";
use FxReport::Rates;

my $today = { EURUSD => { close => 1.1000, high => 1.11, low => 1.09, avg => 1.1 } };
my $prev  = { EURUSD => { close => 1.0000 } };
my $rows  = FxReport::Rates::moves($today, $prev);
is(scalar @$rows, 1, 'one pair');
cmp_ok(abs($rows->[0]{chg_pct} - 10), '<', 1e-9, 'ten percent move');
ok(!defined FxReport::Rates::moves($today, undef)->[0]{chg_pct}, 'no previous day, no change');

my $dir = tempdir(CLEANUP => 1);
open my $fh, '>', "$dir/rates-2026-10-14.csv" or die $!;
print $fh "pair,open,high,low,close,avg_mid,ticks\nEURUSD,1.08,1.11,1.07,1.10,1.09,24\n";
close $fh;
my $legacy = FxReport::Rates::read_day("$dir/rates-2026-10-14.csv");
is($legacy->{EURUSD}{business_date}, '2026-10-14', 'legacy spool gets its business date from dated filename');

open $fh, '>', "$dir/rates-2026-10-15.csv" or die $!;
print $fh "pair,open,high,low,close,avg_mid,ticks,business_date\nEURUSD,1.08,1.11,1.07,1.10,1.09,24,2026-10-15\n";
close $fh;
my $dated = FxReport::Rates::read_day("$dir/rates-2026-10-15.csv");
is($dated->{EURUSD}{business_date}, '2026-10-15', 'batch business date is carried with the figure');
is(FxReport::Rates::moves($dated, $legacy)->[0]{business_date}, '2026-10-15', 'report row retains the rate date');
done_testing();
