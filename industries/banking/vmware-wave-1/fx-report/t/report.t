use strict;
use warnings;
use Test::More;
use FindBin;
use File::Temp qw(tempdir);

my $dir = tempdir(CLEANUP => 1);
for my $day ('2026-10-14', '2026-10-15') {
    open my $fh, '>', "$dir/rates-$day.csv" or die $!;
    print $fh "pair,open,high,low,close,avg_mid,ticks,business_date\nEURUSD,1.08,1.11,1.07,1.10,1.09,24,$day\n";
    close $fh;
}
local $ENV{RATES_OUT_DIR} = $dir;
local $ENV{REQUEST_METHOD} = 'GET';
local $ENV{QUERY_STRING} = 'day=2026-10-15';
open my $cgi, '-|', $^X, '-I', "$FindBin::Bin/../lib", "$FindBin::Bin/../cgi-bin/fx-report.cgi" or die $!;
my $html = do { local $/; <$cgi> };
close $cgi;
is($?, 0, 'CGI exits successfully');
like($html, qr/<td>1\.10 \(2026-10-15\)<\/td>/, 'close has adjacent business date');
like($html, qr/<td>1\.09 \(2026-10-15\)<\/td>/, 'average has adjacent business date');
like($html, qr/<td>0\.04000 \(2026-10-15\)<\/td>/, 'range has adjacent business date');
done_testing();
