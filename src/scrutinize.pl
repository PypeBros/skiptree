use strict;
my %net=();

my %treenodes=();
my %treelinks=();
my %target;

my %tag=(TEST=>'?%',
	 OORANGE=>'color=red',
	 HOP=>'+%');

sub parse_neighbourhood {
  my $nghb = $_[0];
  $nghb=~/^\<Node--(.*), \<Neighbourhood--\|(.*)\|\>\>/ or die "not a neighbourhood declaration";
  my $thisnode=$1;
  my @rings = split /\|\|/,$2;
  
}

# extract nodes names and link relationships. return leaf ID.
# (Idst > 00001388 (Idst)) & (Isrc > 558b5f84 (Isrc)) & (Idst < 00001940 (Idst)) & (Tdst < 3f59 (Tdst))
sub process_cpe {
  my $tag=shift @_;
  my $nname=shift @_;
  my @textcpe=@_;
  my $parent=undef;
  my ($nlabel, $ndir, $id, $lastdir)=();
  my $termno=1;
  print STDERR join ';',@textcpe;
  foreach(@textcpe) {
    next if length($_)==0;
    if (/\(([A-Z][a-z]+) ([<=>]) ([0-9a-zA-Z]+)/) {
      $nlabel="$1 ? $3";
      $ndir = $2;
      my $tval = $target{$1};
      $ndir = '>>' if $ndir eq '>' && $tval gt $3;
      $ndir = '<<' if $ndir eq '<' && $tval lt $3;
      print STDERR "[$1: $tval <?> $3]\n";
    } else {
      die "unknown term # $termno in equation: $_";
    }
    $termno++;
    
    if (!exists $treenodes{$nlabel}) {
      $id = "n".int(keys %treenodes);
      $treenodes{$nlabel}=$id;
    } else {
      $treenodes{$nlabel}=~/^(n\d+)/;
      $id = $1;
    }
    if (defined $parent) {
      $treelinks{"$parent--$id"}=$lastdir;
      # TODO: bold links if they match %target information.    
    }
    $lastdir=$ndir;
    $parent=$id;
  }
  # and add the node at the tail of the path.
  my $tid=undef;
  if (exists $treenodes{$nname}) {
    $tid=(split/,/,$treenodes{$nname})[0];
  } else {
    $tid="l".int(keys %treenodes);
    $treenodes{$nname}=$tid;
  }
  $treelinks{"$id--$tid"}=$lastdir;
  $treenodes{$nname}.=",$tag";
}

# extract infos from a Node.pname() report.
sub split_node {
  print STDERR "# ",substr($_[0],0,75),"...\n";
  
  $_[0]=~/<Node--\d+-?-?([0-9.]*), <NameID::([a-z0-9]+)> :: EQ:-(.*?)\/EQ> (.*)/ or return;
  
  print STDERR "# $2 @ $1 ::= $3\n";
  print STDERR "#... ",substr($4,0,60),"...\n";
  return ($2,$3,$1,$4);
}

# suitable for a "no destination" dump from a RouterVisitor.
sub parse_log {
  my $log = $_[0];
  $log =~ /\<RCPE (LRQ#[0-9.]+) to \<\@:(.*)\@\>\> in \<Router.isitor:\[('.*')\]> --tr: \[('.*')\]/
    or die "not a message log";
  my ($id, $target, $rlog, $mlog)=($1,$2,$3,$4);
  
  my @vals = split /\)/,$target;
  foreach (@vals) {
    length($_)>0 or next;
    /=([0-9a-z]+) \(([A-Z][a-z]+)/ or die "wrong format for val $_ in target";
    $target{$2}=$1;
  }
  my $nvals=int(keys %target);
  print STDERR "$nvals values in target.\n";
  
  # processing the failed node's log.
  my ($rp,$nname,$ncpe,$npid) = ($rlog);
  while (length($rp)>0) {
    ($nname, $ncpe, $npid,$rp)=split_node($rp); 
    last if !defined $nname;
    $ncpe=~s/ \([A-Z][a-z]+\)\)/\)/g;
      
    my $how="TEST";
    if($rp=~/\@ [0-9a-f]+ \((\d+), ([0True]+)\)',[^']+(.*)/) {
      $how.=":$1";
      $rp=$3;
    }
    $how.=',OORANGE' if $rp=~/^'[^']+out of partition range[^']+/;
    process_cpe($how,$nname.':'.$npid, split(/&/,$ncpe));
  }
  
  $rp=$mlog; # processing the message's route log.
  my $hopno=0;
  while (length($rp)>0) {
    ($nname, $ncpe, $npid,$rp)=split_node($rp); 
    last if !defined $nname;
    $ncpe=~s/ \([A-Z][a-z]+\)\)/\)/g;
    print STDERR "\t$nname ::= $ncpe\n";
    process_cpe("HOP:$hopno","$nname:$npid", split/&/,$ncpe);
    $hopno++;
  }
}

# suitable to diagnose a message that comes back with !_! DATA and !_! PATH
sub parse_path {
  my $log = $_[0];
  chomp $log;
  die "no multi-line (...$1\\n$2...)" if $log=~/(.{0,20})\n(.{0,20})/m;
  #                            first reply v       more replies v   v newline?
  $log =~ /!_! DATA ([0-9.]+) - \[\(\<\@:(.*?)\@\>, \[[^]]*\]\).*\].*!_! PATH \[('.*')\]/
    or die "not a message path\n".substr($log,0,20)."...".substr($log,-20,20);
  my ($id, $target, $mlog)=($1,$2,$3,);
  
  my @vals = split /\)/,$target;
  foreach (@vals) {
    length($_)>0 or next;
    /=?([0-9a-z]+) \(([A-Z][a-z]+)/ or die "wrong format for val $_ in target";
    $target{$2}=$1;
  }
  my $nvals=int(keys %target);
  print STDERR "$nvals values in target.\n";

  my ($rp,$nname,$ncpe,$npid) = ($mlog);
  my $hopno=0;
  while (length($rp)>0) {
    ($nname, $ncpe, $npid,$rp)=split_node($rp); 
    last if !defined $nname;
    $ncpe=~s/ \([A-Z][a-z]+\)\)/\)/g;
    print STDERR "\t$nname ::= $ncpe\n";
    process_cpe("HOP:$hopno","$nname:$npid", split/&/,$ncpe);
    $hopno++;
  }
}

my $data='';
while ($_=<>) {
  parse_log($_) if /RCPE .LRQ/;
  parse_path($data.$_) if /!_! PATH/;
  if (/!_! DATA/) {
    chomp;
    $data=$_;
    next;
  } else{
    $data='';
  }

}
    
print <<___
graph {

   ordering=out
___
;

foreach(keys %treenodes) {
  my $title=$_;
  my @attr=split /,/,$treenodes{$_};
  my $node=shift @attr;
  my $shape= $node=~/^l/ ? "box" : "parallelogram";
  my @more=();

  # apply values and template substitution on tags.
  foreach (@attr) {
    my ($key,$val)=split /:/;
    my $templ=$tag{$key};
    $templ="'$key=%'" unless exists $tag{$key};
    $templ=~s/%/$val/;
    if ($templ=~/=/) {
      push @more,$templ;
    } else {
      $title.=" $templ";
    }
  }

  # produce the node
  print "\t$node [label=\"$title\" shape=$shape ",join(' ',@more),"]\n";
  $treenodes{$_}=$node; # drop all the "decorating" attributes.
}

my @all=keys %treelinks;
my @leftwards = grep {$treelinks{$_} le '<<'} @all;
my @rightwards= grep {$treelinks{$_} ge '>'} @all;
my @inodes = keys %treenodes;
print "# @inodes\n";
@inodes = grep {/\?/} @inodes; # substr($treenodes{$_},0,1) eq 'n'
print "# @inodes\n";

foreach(@leftwards) {
  s/^--/NOCPE--/;
  print "$_ [label=\"$treelinks{$_}\"","]\n";
}  

foreach(@inodes) {
  my $id = $treenodes{$_};
  print "x$id [label=\"\" shape=circle color=white]\n";
  print "$id--x$id [color=white fontcolor=white]\n";
}

foreach(@rightwards) {
  s/^--/NOCPE--/;
  print "$_ [label=\"$treelinks{$_}\"","]\n";
}  


print "}\n";
