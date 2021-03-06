#!/usr/bin/perl
use Socket;
use IO::Handle; # for flushes
use strict;


my $port=8086;     # first port we will try
my $lastport=8100; # port we'll stop at.

socket(LISTEN, PF_INET, SOCK_STREAM, getprotobyname('tcp')) or die 'socket(t)';
setsockopt(LISTEN, SOL_SOCKET, SO_REUSEADDR, 1);

my $myname = `uname -n`;
chomp $myname;
my $myaddr=gethostbyname($myname);
$myaddr=inet_aton($myaddr) if length $myaddr>4;
my $TADDR =inet_ntoa($myaddr);
print STDERR "$myname = $TADDR\n";
my $la = sockaddr_in($port,$myaddr);

# --- bind them ---
# both sockets need to be bound so that source port of advertisments is $port
# and that we listen for TCP connections on the same $port.
bind(LISTEN, $la) or die "SOMEONE STPPED ON MCP CHANNEL. EOL\n";
listen LISTEN, 2048;

welcome();
print STDERR "BOUND AND LISTENING\n";
open LOG, ">MCP.now" or die "you want logging on MCP.now, don't you?";
select LOG; $|=1; select STDOUT;
print LOG "BOUND AND LISTENING\n";


# --- process state ---
my $CONTACT="$TADDR:8080";   # who you should talk to.
my @pending=();              # sockets handles waiting for processing
my @ready=();                # sockets handles waiting for commands.
my $status='FREE';           # turns to 'BUSY' while a peer connects.
my $reporting=0;

# --- the loop ---
my $FH;
my $who;

while(1) {
  # -- if there's a pending connection, we end up here.
  my ($remport,  $remaddr);
  eval {
    $FH=undef;
    ($remport,  $remaddr) = sockaddr_in(accept($FH,LISTEN));
    # -- we want to ensure that only the DS can request the file.
    #    this is not public offer.
  };
  print STDERR "connection received from ".inet_ntoa($remaddr)."\n";
  last if !defined $FH;
  eval {
    $who=<$FH>;
    my @info=();
    # ---  process control commands from the user ---
    if ($who=~/GET ([a-z0-9A-Z]+)/) {
      print STDERR "EPOCH $1 OVER. $#ready NODES NOTIFIED\n";
      print LOG "EPOCH $1 OVER. $#ready NODES. ", `date`;
      my @ping=@ready;
      @ready=();
      foreach(@ping) {
	if ($1 eq 'debug') {
	  print $_ "TYPE 8;\r\n";
	} else {
	  print $_ "TYPE 0;6;\r\n";
	}
	print $FH $_;
	$reporting++;
#	print $FH getmessage($_);
	close $_;
      }
      next; # done. We'll got replies on another channel.
    }	
    if ($who=~/TRON/) {
      print $FH "END Of LINE\n";
      close $FH;
      foreach(@pending) {
	print $_ "KILL \r\n";
	close $_;
      }
      close LISTEN;
      exit 0;
    }
    $who =~ s/[\r\n]+$//;
    @info=getmessage($FH);

    # --- process reports/requests from planetlab nodes ---
    print STDERR "$#info entries : @info\n";
    if ( $status eq 'FREE' && $info[-1]=~/ READY/){
      dojoin($CONTACT);
    } elsif ($status eq 'BUSY' && $info[-1]=~/ READY/) {
      enqueue();
    } elsif ($status eq 'BUSY' && $info[-1]=~/ CONNECTED/) {
      dequeue();
    } elsif ($info[-1] =~ /beat/) {
      print LOG "$who ack heartbeat\n";
      noop($FH);
      $reporting--;
      print STDERR "$reporting NODE REPORT(s) STILL MISSING" if $reporting;
      print STDERR "ALL NODES HAVE REPORTED" if !$reporting
    } else {
      print STDERR "unexpected $who '$info[-1]' in state $status\n";
      noop($FH);
    }
  } ;
  print STDERR "ERROR $@\n" if $@;
}
close LISTEN;

exit 0;



sub getmessage {
  my @nfo=();
  my $fh = $_[0];
  my $d;
  while ($d=<$fh>) {
    print STDERR "# $d";
    last if !defined $d;
    next unless $d =~ /_/;
    $d =~ s/[\r\n]+$//;
    push @nfo, $d;
    print LOG "$who - $d\n";
    last if $d=~/^#_# /;
  }
  return @nfo;
}


sub dojoin {
  my ($ip,$port)=split /:/,$_[0];
  print STDERR "JOIN GRANTED ($ip:$port)\n";
  print LOG "JOIN GRANTED ($ip:$port)\n";
  print $FH "TYPE 2;$port;$ip;\r\n";
  close $FH; # peer will come back with another connection.
  $status='BUSY';
}

sub enqueue {
  push @pending,$FH; # we haven't replied yet.
  undef $FH;
}

sub dequeue {
  print STDERR "CONNECTION ACKNOWLEDGED $FH\n";
  print LOG "CONNECTION ACKNOWLEDGED $FH\n";
  print $FH "WAIT\r\n"; 
  $FH->autoflush(1);
  push @ready, $FH; # let's keep it for later.
  if (@pending) {
    $FH=shift @pending;
    dojoin($CONTACT);
  } else {
    print STDERR "ALL THE PROGRAMS JOINED THE GRID. EOL\n";
    $status='FREE';
  }
}

sub noop {
  my $fh=$_[0];
  $fh->autoflush(1);
  print $fh "WAIT\r\n"; #  close $FH;
  push @ready, $fh;
}

sub welcome {
print STDERR <<___
................,,,:,,=====~~::~~~~~~====~~~~~~~::~~====~:,:,,,..,.............,
................,,:,:~=====~~~~~~~~~~====~~~~~:~~:~~~=====~,,,,..,.......,......
................,,:,:~===~:::::~:~~~~====~~~~~~~::::~====~~:::,.................
................,::::===~~~~~~~~~~~~~=====~~~~~~::~~~~~==~~:,,.....,............
................,,:~~=~===~~~~::~~~~=======~~~~~~~~~~=====~,,,,....,,,.....,....
.........,,......,,~~===~:::~~~~~~~~=======~~~~~:~~:::==+=~,,,......,,,.........
........,,.....,.,,:==~=+=~~~~~~~~~~======~~~~~~:~~~~==+:==:,,......,,,.........
.......,,,,,.....,,:~:===~~~~~::::~~======~~~:::~~~~~====:=:,,...,,,,,,,.....,..
......,,,,,,,,,,,,,~=+===~~~:~::~~~~======~~~~~::~~~~~==++=~,,,,,,,,,,:,,.,...,.
......,:,,,,,,,,,,,~=+===~~~~~~~~~~~=======~~~~~~~~~~~===+=~,::::,,::,:,,,,.....
...,,,,:,,,,,:,:,,:======~~:~~~~::::~~~~~~~~:::~~~~~~~~==++=::::~::::::::,,,,,..
...,,:::::,::::~::======~~~~::::::::~~~~~~~::::::::~~~~=====~:::::,:::::::,,,,..
,.,,:,:,:::::::::~==+===~~::::::::~~~~==~=~~~::::::::~~===+==:::::::::~~~::,,,,.
.,,,:~::~::::::~~~=++==~~:~~~~~~~~~~=======~~~~~~~~~::~===++=~~:~~~~::~:~::,,,,,
,,,::~~:::::::~==~=++===~~~~~~~~~~~~=======~~~~~~~~~~~~===++=~~~~===~::::~~:,,,,
,,,:~~::::~=~~===~==+===~~~~~~~~~~~~=======~~~~~~~~~~~~=====+~==~~~~~::::~~~,,,,
,,:~~~~:~~====++=~=+===~~~~~~~~~~~~~========~~~~~~~~~~~~==+==~~========~~~~::,,,
,:::~~=~~~++++====+====~~~~~~~~~~~~~=======~~~~~~~~~~~~~====+==~~~~~===~~::~::,:
::::::~~~~=++==+=+=====~~~~~~~~~~~~~=======~~~~~~~~~~~~===========~~=~~~::::::::
:,:::::~~~~==~=+~=++=====~~~~~~~~~~~=======~~~~~~~~~~=====+++=====+===~~::::~:::
:~:,:::~==:~~~~===+++====~~~~~~~~~~~~=====~~~~~~~~~~=====++++==++==~~=~~::::~:::
,::,,,:~==~===~~~====++====~~~~~~~~~~====~~~~~~~~~~~===+++++==~~~==~~~:::::::~~:
::::,,,,~~~===~:~~~==++++===~~~~~~~~~=====~~~~~~~~====+++===~~~~~+==~::,,::::~:~
::::,,,,,,:~===~~~~~~===++===~~~~~~~~====~~~~~~~~===+++===~~~~~=+===~::,,,::::~~
=::,,,,:,,:::~~+++=~:~~===++===~~~~~~~===~~~~~~~===++==~~~~~==+==~~::,,,,:::::==
=~===,,,,:,::~~~~~+?+=~~~~==++==~~~~~~===~~~~~~==++==~~~~=+?+~~~~~::::,~,,===~==
=========::::~~~~~:~:~?+=~~~~====~~~~~==~~~~~~====~~~~=+?~~~:~~~~~::::==========
==~==========:~:::::~~:~==?+~~~===~~:~==~~:~====~:~+?~~~~~::::::~~==========~===
==~==========~~:::,,~:::::~===+~:=+=~~~=~~~=+~:=?~~~=~~~::::::::~:==============
___
  ;
}
