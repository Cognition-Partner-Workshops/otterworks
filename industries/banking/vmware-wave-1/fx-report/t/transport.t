use strict;
use warnings;
use Test::More;
use FindBin;

# The sign-in config must keep desk passwords off the wire in clear text:
# browser to Apache and Apache to the directory both run over TLS.
my $conf = "$FindBin::Bin/../vm/fx-report.conf";
open my $fh, '<', $conf or die "$conf: $!";
my @lines = grep { !/^\s*(#|$)/ } map { s/\s+$//r } <$fh>;
close $fh;

my (@blocks, $cur);
for (@lines) {
    if (/^\s*<(Directory|Location|Files)\b/i) { $cur = []; push @blocks, $cur; next }
    if (/^\s*<\/(Directory|Location|Files)>/i) { undef $cur; next }
    push @$cur, $_ if $cur;
}

my @urls = map { /^\s*AuthLDAPURL\s+"?(\S+?)"?(?:\s+(\S+))?$/i ? [$1, $2 // ''] : () } @lines;
ok(@urls, 'directory sign-in is configured');
for (@urls) {
    my ($url, $mode) = @$_;
    ok($url =~ m{^ldaps://}i || $mode =~ /^(SSL|TLS|STARTTLS)$/i, "AuthLDAPURL $url binds over TLS");
}
ok(!grep(/^\s*LDAPVerifyServerCert\s+Off/i, @lines), 'directory certificate is verified');
ok(grep(/^\s*LDAPTrustedGlobalCert\s+CA_BASE64\s+\S+/i, @lines), 'directory CA is configured');
ok(grep(/^\s*LoadModule\s+ssl_module\b/i, @lines), 'mod_ssl is loaded for SSLRequireSSL');

my @basic = grep { grep /^\s*AuthType\s+Basic/i, @$_ } @blocks;
ok(@basic, 'Basic sign-in block found');
ok(grep(/^\s*SSLRequireSSL\b/i, @$_), 'Basic sign-in only accepted over HTTPS') for @basic;

done_testing;
