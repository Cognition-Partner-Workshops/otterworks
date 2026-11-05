use strict;
use warnings;
use Test::More;
use File::Temp qw(tempdir);
use FindBin;
use lib "$FindBin::Bin/../lib";
use FxReport::Rates;

my $dir = tempdir('fs09_fx_XXXXXX', TMPDIR => 1, CLEANUP => 1);
sub write_rates {
    my ($file, $date, $close) = @_;
    open my $fh, '>', "$dir/rates-$file.csv" or die $!;
    print $fh "pair,open,high,low,close,avg_mid,ticks,business_date\n";
    print $fh "EURUSD,1.08,1.11,1.07,$close,1.09,24,$date\n";
    close $fh;
}
sub report {
    my ($query) = @_;
    local $ENV{RATES_OUT_DIR} = $dir;
    local $ENV{REQUEST_METHOD} = 'GET';
    local $ENV{QUERY_STRING} = $query;
    local $ENV{TZ} = 'Pacific/Kiritimati';
    open my $cgi, '-|', $^X, '-I', "$FindBin::Bin/../lib", "$FindBin::Bin/../cgi-bin/fx-report.cgi" or die $!;
    my $html = do { local $/; <$cgi> };
    close $cgi;
    return $html;
}

write_rates('2026-11-01', '2026-10-31', '1.10');
write_rates('2026-10-31', '2026-10-30', '1.00');
my $html = report('day=2026-11-01');
like($html, qr/\+10\.000% \(2026-10-31 vs 2026-10-30\)/,
    'change figure dates both source rates, including across month boundaries');
like($html, qr/Report file date 2026-11-01/, 'header does not mislabel a file date as the rate business date');
like($html, qr/<td>1\.10 \(2026-10-31\)<\/td>/, 'close uses rate business date, not host clock or requested file date');
like($html, qr/<td>1\.09 \(2026-10-31\)<\/td>/, 'average uses source date');
like($html, qr/<td>0\.04000 \(2026-10-31\)<\/td>/, 'range uses source date');
my $missing = report('day=2026-12-02');
like($missing, qr/No rates file/, 'missing file prints no unlabelled rates');
my $invalid = report('day=not-a-date');
like($invalid, qr/Status: 400/, 'invalid date returns a generic client error');
unlike($invalid, qr/not-a-date/, 'invalid query is not reflected');

open my $fh, '>', "$dir/rates-2026-12-01.csv" or die $!;
print $fh "pair,open,open_business_date,high,high_business_date,low,low_business_date,close,close_business_date,avg_mid,avg_mid_business_date,ticks,business_date\n";
print $fh "EURUSD,1.08,2026-12-01,1.11,2026-12-01,1.07,2026-12-01,1.10,2026-12-01,1.09,2026-12-01,24,2026-12-01\n";
close $fh;
my $rates = FxReport::Rates::read_day("$dir/rates-2026-12-01.csv");
is($rates->{EURUSD}{close}, '1.10', 'report reads adjacent-date CSV without shifting rate columns');
is($rates->{EURUSD}{business_date}, '2026-12-01', 'CSV source business date survives');
like(report('day=2026-12-01'), qr/<td>1\.10 \(2026-12-01\)<\/td>/, 'adjacent-date CSV renders correctly');
open $fh, '>', "$dir/rates-2026-12-03.csv" or die $!;
print $fh "pair,open,high,low,close,avg_mid,ticks,business_date\n";
close $fh;
unlike(report('day=2026-12-03'), qr/<td>/, 'empty file prints no rate figures');
done_testing();
