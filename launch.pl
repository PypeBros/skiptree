#!/usr/bin/perl

# cat ulgple_disco.nodes | fe - "rsync launch.pl ulgple_disco@%: ; echo %"
# cat ulgple_disco.nodes | fe - "rsync skiptree-clerinx/ResumeNet/join.data ulgple_disco@%: ; echo %"
# cat ulgple_disco.nodes | fe - "ssh ulgple_disco@% -C 'perl launch.pl'&"

use Socket;

$MYSELF=0+$ARGV[0];

## configuration: where is the Master Control Program ?
$MCP_IP = "139.165.223.18";
$MCP_PORT= 8086;
$TRACING=''; # off
system "killall python3";
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
$FIFO = "$NAME-2818$MYSELF.cmd";
# establish the communication path with the python node.


print STDERR "[[CLU rev $launchdate - $NAME = $IP ($NUM)]]\n";
print STDERR "[- running DISco rev $sourcedate -]\n";

if (-e $FIFO && ! -p $FIFO) {
  print STDERR "[- replacing $FIFO -]\n";
  unlink $FIFO;
}

print STDERR "[- will talk through $FIFO -]\n";
system "mkfifo $FIFO" unless -e $FIFO;

print STDERR "[- launching skiptree python -]\n";
open DONE,"$TRACING python3 src/__main__.py $IP 2818$MYSELF $nameID $NUM < $FIFO |" or die "cannot launch";

# opening FIFO for writing blocks unless there's a reader already.
open CMD,"> $FIFO" or die "no FIFO for commands\n";
select CMD ; $|=1 ; select STDOUT;


  # run the main control loop.
  
eval {
  print CMD "0\n3\n0_0 HELLO\n"; # echoes the HELLO message
  print CMD "0\n4\n5\n"; # sleeps (the stdin reader thread) for 5 second
  print CMD "0\n3\n#_# READY\n"; # echoes the READY message.
#  sleep 5;
  print STDERR "[- waiting for acknowledgement -]\n";
  
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
      $commands=<MASTER>;
      print STDERR "[$NUM\[$NAME wait is over]]\n";
    }
    if ($commands=~/^TYPE (.*)/) {
      chomp $1;
      print STDERR "[$NUM\[$NAME typing commands $1]]\n";
      @lines = split /;/,$1;
      foreach (@lines) {
	print CMD "$_\n";
      }
      print STDERR " done.\n";
      close MASTER;
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
      close MASTER;
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
};
print STDERR "LAUNCHER FOR $nameID @ $NAME DIED !?\n --  $@ $!\n -- $?\n";
print CMD "0\n3\nAOUCH\n7\n";
exit -1;

sub wait_for_next_step {
  my $Pip = inet_aton($MCP_IP);
  $reason= $_[-1];
  chomp $reason;
  
  my $port = $MCP_PORT;
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
}

sub filetag {
  @t=localtime((stat($_[0]))[9]);
  return "$t[5]$t[3]$t[3].$t[2]$t[1]";
}
