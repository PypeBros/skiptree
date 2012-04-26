#!/usr/bin/perl

# cat ulgple_disco.nodes | fe - "rsync launch.pl ulgple_disco@%: ; echo %"
# cat ulgple_disco.nodes | fe - "rsync skiptree-clerinx/ResumeNet/join.data ulgple_disco@%: ; echo %"
# cat ulgple_disco.nodes | fe - "ssh ulgple_disco@% -C 'perl launch.pl'&"

use Socket;

$MYSELF=0+$ARGV[0];

## configuration: where is the Master Control Program ?
$MCP_IP = "139.165.223.18";
$MCP_PORT= 8086;
#$TRACING ="strace -enetwork -f -s512 -o /tmp/py.trace";
$TRACING=''; # off

# define the local variables.

$NAME=`uname -n`;
chomp $NAME;
$IP  =gethostbyname($NAME);
$IP = inet_ntoa($IP) if defined $IP;
my $NUM = int(rand(100));
$sourcedate=filetag("src/__main__.py");
$launchdate=filetag("launch.pl");

{
  my @base32=('a'..'z', 0..5);
  $nameID = join '', (map $base32[rand(@base32)], (0..4));
}

# establish the communication path with the python node.

print STDERR "[[CLU rev $launchdate - $NAME = $IP ($NUM)]]\n";
print STDERR "[- running DISco rev $sourcedate -]\n";
system "mkfifo $NAME-2808$MYSELF.cmd" unless -e "$NAME-2808$MYSELF.cmd";
open DONE,"$TRACING python3 src/__main__.py $IP 2808$MYSELF $nameID $NUM < $NAME-2808$MYSELF.cmd |" or die "cannot launch";
open CMD,">$NAME-2808$MYSELF.cmd" or die "no FIFO for commands";
sleep 5;

# run the main control loop.

select CMD ; $|=1 ; select STDOUT;
print CMD "0\n3\n0_0 HELLO\n0\n3\n#_# READY\n";

while (<DONE>) {
  /^[#0]_[#0] / or next;
  print STDERR ">$NUM> $_";
  push @report,$_;
  next if /^0_0 /;
  # messages starting with 0_0 are informative,
  # messages starting with #_# denote state changes.

  print STDERR "$NAME reported $_";
  $commands = wait_for_next_step(@report);
  @report=();
  if ($commands=~/^WAIT/) {
    next;
  }
  if ($commands=~/^TYPE (.*)/) {
    print STDERR "[$NUM\[$NAME typing commands $1]]\n";
    @lines = split /;/,$1;
    foreach (@lines) {
      print CMD "$_\n";
    }
  }
  if ($commands=~/^LOAD (.*)/) {
    # there's intentionally no protection on remotely sent request to
    #  run process through this command, so that we can zcat or csv2py
    #  on the fly.
    my $cmd = $1;
    open DATA,"$cmd" or die "unable to LOAD $cmd";
    my $count=0;
    while(<DATA>) {
      print CMD; $count++;
    }
    print STDERR "[$NUM\[ $count statements produced from $1]]\n";
  }
  if ($commands=~/^QUIT/) {
    close CMD;
  }
  if ($commands=~/^KILL/) {
    system "killall python3";
    system "killall tail";
    exit 0;
  }
}

sub wait_for_next_step {
  my $Pip = inet_aton($MCP_IP);
  my $port = $MCP_PORT;
  $reason= $_[-1];
  chomp $reason;
  print STDERR "[$NUM\[contacting master: $reason]]\n";
  socket(MASTER, PF_INET, SOCK_STREAM, getprotobyname('tcp')) or die "socket2MCP";
  my $paddr= sockaddr_in($port, $Pip);
  connect(MASTER,$paddr) or die "[$NUM!connect to MCP!]";
  print MASTER "DONE $IP:$NUM\r\n";
  select MASTER; $|=1; select STDOUT;
  print MASTER join("\r\n",@_),"\r\n\r\n";
  my $ack=<MASTER>;
  defined $ack or die "[$NUM!no reply from MCP!]";
  return $ack;
  close MASTER;
}

sub filetag {
  @t=localtime((stat($_[0]))[9]);
  return "$t[5]$t[3]$t[3].$t[2]$t[1]";
}
