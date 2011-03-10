################################################################################
#
#   Gene prediction pipeline 
#
#   $Id: gtf2gtf.py 2861 2010-02-23 17:36:32Z andreas $
#
#   Copyright (C) 2004 Andreas Heger
#
#   This program is free software; you can redistribute it and/or
#   modify it under the terms of the GNU General Public License
#   as published by the Free Software Foundation; either version 2
#   of the License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA  02111-1307, USA.
#################################################################################
'''
gtf2gtf.py - manipulate gtf files
=================================

:Author: Andreas Heger
:Release: $Id$
:Date: |today|
:Tags: Python

Purpose
-------

This scripts reads a :term:`gtf` formatted file from stdin, applies some
transformation, and outputs a new :term:`gtf` formatted file to stdout.

This script expects the gtf file to be sorted by genes and then by 
position.

Usage
-----

Example::

   python <script_name>.py --help

Type::

   python <script_name>.py --help

for command line help.

Documentation
-------------

Code
----

'''
import os, sys, string, re, optparse, types, random, collections

import GFF,GTF
import Experiment as E
import IndexedFasta
import Genomics
import Intervals
import IOTools
import Components

##------------------------------------------------------------
## This script needs some attention.
##------------------------------------------------------------
if __name__ == '__main__':

    parser = optparse.OptionParser( version = "%prog version: $Id: gtf2gtf.py 2861 2010-02-23 17:36:32Z andreas $", usage = globals()["__doc__"])

    parser.add_option("-m", "--merge-exons", dest="merge_exons", action="store_true",
                      help="merge overlapping exons of all transcripts within a gene [default=%default]."  )

    parser.add_option( "--merge-exons-distance", dest="merge_exons_distance", type="int",
                      help="distance to merge exons over [default=%default]."  )

    parser.add_option( "--unset-genes", dest="unset_genes", type="string",
                      help="unset gene identifiers, keeping transcripts intact,"
                       " set to pattern [default=%default]."  )

    parser.add_option( "--merge-genes", dest="merge_genes", action="store_true",
                      help="merge overlapping genes if their exons overlap. This ignores the strand [default=%default]."  )

    parser.add_option( "--sort", dest="sort", type="choice",
                       choices=("gene", "transcript", "position", "contig+gene", "position+gene" ),
                       help="sort input [default=%default]."  )

    parser.add_option("-u", "--with-utr", dest="with_utr", action="store_true",
                      help="include utr in merged transcripts [default=%default]."  )

    parser.add_option("-t", "--merge-transcripts", dest="merge_transcripts", action="store_true",
                      help="merge all transcripts within a gene. The entry will span the whole gene (exons and introns). The transcript does not include the UTR unless --with-utr is set. [default=%default]."  )

    parser.add_option( "--intersect-transcripts", dest="intersect_transcripts", action="store_true",
                      help="intersect all transcripts within a gene. The entry will only span those bases "
                      " that are covered by all transcrips."
                      " The transcript does not include the UTR unless --with-utr is set. This options"
                      " will remove all other features (stop_codon, etc.) "
                      " [default=%default]."  )

    parser.add_option("-i", "--merge-introns", dest="merge_introns", action="store_true",
                      help="merge all introns within a gene [default=%default]."  )

    parser.add_option("-g", "--set-transcript-to-gene", "--set-transcript2gene", dest="set_transcript2gene", action="store_true",
                      help="set the transcript_id to the gene_id [default=%default]."  )

    parser.add_option( "--set-protein-to-transcript", dest="set_protein2transcript", action="store_true",
                      help="set the protein_id to the transcript_id [default=%default]."  )

    parser.add_option( "--add-protein-id", dest="add_protein_id", type="string",
                      help="add the protein_id for each transcript_id. The argument is a filename with a map [default=%default]."  )

    parser.add_option("-G", "--set-gene-to-transcript", "--set-gene2transcript", dest="set_gene2transcript", action="store_true",
                      help="set the gene_id to the transcript_id [default=%default]."  )

    parser.add_option("-d", "--set-score2distance", dest="set_score2distance", action="store_true",
                      help="set the score field to the distance to transcription start [default=%default]."  )

    parser.add_option( "--exons2introns", dest="exons2introns", action="store_true",
                       help="convert exons to introns for a gene. Introns are labelled with the feature 'intron'." )

    parser.add_option("-f", "--filter", dest="filter", type="choice",
                      choices=("gene", "transcript","longest-gene"),
                      help="filter by gene-id or transcript-id. If `longest-gene` is chosen, the longest gene is chosen case of overlapping genes [default=%default]."  )

    parser.add_option("-r", "--rename", dest="rename", type="choice",
                      choices=("gene", "transcript","longest-gene"),
                      help="rename genes or transcripts with a map given in apply. Those that can not be renamed are removed [default=%default]."  )

    parser.add_option( "--renumber-genes", dest="renumber_genes", type="string", 
                      help="renumber genes according to pattern [default=%default]."  )

    parser.add_option( "--renumber-transcripts", dest="renumber_transcripts", type="string", 
                      help="renumber transcripts according to pattern [default=%default]."  )

    parser.add_option("-a", "--apply", dest="filename_filter", type="string",
                      help="filename to filter with [default=%default]."  )

    parser.add_option( "--invert-filter", dest="invert_filter", action="store_true",
                      help="invert filter (like grep -v) [default=%default]."  )

    parser.add_option("--sample-size", dest="sample_size", type="int",
                      help="extract a random sample of size # if the option --filter is set[default=%default]." )

    parser.add_option("--intron-min-length", dest="intron_min_length", type="int",
                      help="minimum length for introns [default=%default]."  )

    parser.add_option("--min-exons-length", dest="min_exons_length", type="int",
                      help="minimum length for gene (sum of exons) [default=%default]."  )

    parser.add_option("--intron-border", dest="intron_border", type="int",
                      help="number of residues to exclude at intron at either end [default=%default]."  )

    parser.add_option( "--transcripts2genes", dest="transcripts2genes", action="store_true",
                       help="cluster overlapping transcripts into genes." )

    parser.add_option( "--reset-strand", dest="reset_strand", action="store_true",
                       help="remove strandedness of features." )

    parser.add_option( "--remove-overlapping", dest="remove_overlapping", type="string",
                       help="remove all transcripts that overlap intervals in a gff-formatted file."
                       " The comparison ignores strand [%default]." )

    parser.add_option( "--permit-duplicates", dest="strict", action="store_false",
                       help="permit duplicate genes (on different chromosomes, ...) [default=%default]" )

    parser.add_option( "--remove-duplicates", dest="remove_duplicates", type="choice",
                       choices=("gene", "transcript", "ucsc"),
                       help="remove duplicates by gene/transcript. If ``ucsc`` is chosen, transcripts ending on _dup# are removed" 
                       " this is necessary to remove duplicate entries that are next to each other in the sort order [%default]" )

    parser.set_defaults(
        sort = None,
        merge_exons = False,
        merge_exons_distance = 0,
        merge_transcripts = False,
        set_score2distance = False,
        set_gene2transcript = False,
        set_transcript2gene = False,
        set_protein2transcript = False,
        add_protein_id = None,
        filename_filter = None,
        filter = None,
        exons2introns = None,
        merge_genes = False,
        intron_border = None,
        intron_min_length = None,
        sample_size = 0,
        min_exons_length = 0,
        transripts2genes = False,
        reset_strand = False,
        with_utr = False,
        invert_filter = False,
        remove_duplications = None,
        remove_overlapping = None,
        renumber_genes = None,
        unset_genes = None,
        renumber_transcripts = None,
        strict = True,
        intersect_transcripts = False,
        )

    (options, args) = E.Start( parser )
    
    ninput, noutput, nfeatures, ndiscarded = 0, 0, 0, 0

    if options.set_transcript2gene:

        for gff in GTF.iterator(options.stdin):

            ninput += 1

            gff.setAttribute( "transcript_id", gff.gene_id)
            options.stdout.write( "%s\n" % str(gff) )                

            noutput += 1
            nfeatures += 1

    elif options.remove_duplicates:

        counts = collections.defaultdict(int)

        if options.remove_duplicates == "ucsc":
            store = []
            remove = set()
            f = lambda x: x[0].transcript_id

            gffs = GTF.transcript_iterator(GTF.iterator(options.stdin), strict = False)
            outf = lambda x: "\n".join( [ str(y) for y in x] )

            for entry in gffs:
                ninput += 1
                store.append(entry)
                id = f(entry)
                if "_dup" in id: 
                    remove.add(re.sub("_dup\d+","", id) )
                    remove.add( id )

            for entry in store:
                id = f(entry)
                if id not in remove: 
                    options.stdout.write( outf(entry) + "\n" )
                    noutput += 1
                else:
                    ndiscarded += 1
                    E.info("discarded duplicates for %s" % (id))
        else:
        
            if options.remove_duplicates == "gene":
                gffs = GTF.gene_iterator(GTF.iterator(options.stdin), strict = False )
                f = lambda x: x[0][0].gene_id
                outf = lambda x: "\n".join( [ "\n".join( [ str(y) for y in xx] ) for xx in x] )

            elif options.remove_duplicates == "transcript":
                gffs = GTF.transcript_iterator(GTF.iterator(options.stdin), strict = False)
                f = lambda x: x[0].transcript_id
                outf = lambda x: "\n".join( [ str(y) for y in x] )

            store = []

            for entry in gffs:
                ninput += 1
                store.append(entry)
                id = f(entry)
                counts[id] += 1

            for entry in store:
                id = f(entry)
                if counts[id] == 1:
                    options.stdout.write( outf(entry) + "\n" )
                    noutput += 1
                else:
                    ndiscarded += 1
                    E.info("discarded duplicates for %s: %i" % (id, counts[id]))

    elif options.sort:

        entries = list(GTF.iterator(options.stdin))
        if options.sort == "gene":
            entries.sort( key = lambda x: (x.gene_id, x.transcript_id, x.contig, x.start) )
        elif options.sort == "contig+gene":
            entries.sort( key = lambda x: (x.contig,x.gene_id,x.transcript_id,x.start) )
        elif options.sort == "transcript":
            entries.sort( key = lambda x: (x.transcript_id, x.contig, x.start) )
        elif options.sort == "position":
            entries.sort( key = lambda x: (x.contig, x.start) )
        elif options.sort == "position+gene":
            entries.sort( key = lambda x: (x.gene_id, x.start) )
            genes = list( GTF.flat_gene_iterator(entries) )
            genes.sort( key = lambda x: (x[0].contig, x[0].start) )
            entries = IOTools.flatten( genes )

        for gff in entries:
            ninput += 1
            options.stdout.write( "%s\n" % str(gff) )                
            noutput += 1
            nfeatures += 1
            
    elif options.set_gene2transcript:

        for gff in GTF.iterator(options.stdin):

            ninput += 1

            gff.gene_id = gff.transcript_id
            options.stdout.write( "%s\n" % str(gff) )                
            noutput += 1
            nfeatures += 1

    elif options.set_protein2transcript:

        for gff in GTF.iterator(options.stdin):
            ninput += 1
            gff.setAttribute( "protein_id", gff.transcript_id)
            options.stdout.write( "%s\n" % str(gff) )                
            noutput += 1
            nfeatures += 1

    elif options.add_protein_id:

        transcript2protein = IOTools.readMap( open( options.add_protein_id, "r") )

        missing = set()
        for gff in GTF.iterator(options.stdin):
            ninput += 1
            if gff.transcript_id not in transcript2protein:
                if gff.transcript_id not in missing:
                    E.debug( "removing transcript '%s' due to missing protein id" % gff.transcript_id)
                    missing.add( gff.transcript_id)
                ndiscarded += 1
                continue
            
            gff.setAttribute( "protein_id", transcript2protein[gff.transcript_id])
            options.stdout.write( "%s\n" % str(gff) )                
            noutput += 1
            nfeatures += 1
        
        E.info("transcripts removed due to missing protein ids: %i" % len(missing))

    elif options.merge_genes:
        # merges overlapping genes
        # 
        gffs = GTF.iterator_sorted_chunks( 
            GTF.flat_gene_iterator(GTF.iterator(options.stdin)),
            sort_by = "contig-strand-start" )
        
        def iterate_chunks( gff_chunks ):

            last = gff_chunks.next()
            to_join = [last]

            for gffs in gff_chunks:
                d = gffs[0].start - last[-1].end

                if gffs[0].contig == last[0].contig and gffs[0].strand == last[0].strand:
                    assert gffs[0].start >= last[0].start, \
                        "input file should be sorted by contig, strand and position: d=%i:\nlast=\n%s\nthis=\n%s\n" % \
                        (d, 
                         "\n".join( [str(x) for x in last] ),
                         "\n".join( [str(x) for x in gffs] ) )

                if gffs[0].contig != last[0].contig or \
                        gffs[0].strand != last[0].strand or \
                        d > 0:
                    yield to_join
                    to_join = []

                last = gffs
                to_join.append( gffs )

            yield to_join
            raise StopIteration
        
        for chunks in iterate_chunks( gffs ):
            ninput += 1
            if len(chunks) > 1:
                gene_id = "merged_%s" % chunks[0][0].gene_id
                transcript_id = "merged_%s" % chunks[0][0].transcript_id
                info = ",".join([ x[0].gene_id for x in chunks ])
            else:
                gene_id = chunks[0][0].gene_id
                transcript_id = chunks[0][0].transcript_id
                info = None

            intervals = []
            for c in chunks: intervals += [ (x.start, x.end) for x in c ]

            intervals = Intervals.combine( intervals )
            # take single strand
            strand = chunks[0][0].strand

            for start, end in intervals:
                y = GTF.Entry()
                y.fromGFF( chunks[0][0], gene_id, transcript_id )
                y.start = start
                y.end = end
                y.strand = strand

                if info: y.addAttribute( "merged", info )
                options.stdout.write( "%s\n" % str(y ) )
                nfeatures += 1

            noutput += 1

    elif options.renumber_genes:
        
        map_old2new = {}
        for gtf in GTF.iterator(options.stdin):
            ninput += 1
            if gtf.gene_id not in map_old2new:
                map_old2new[gtf.gene_id ] = options.renumber_genes % (len(map_old2new) + 1)
            gtf.setAttribute("gene_id", map_old2new[gtf.gene_id ] )
            options.stdout.write( "%s\n" % str(gtf) )
            noutput += 1

    elif options.unset_genes:
        
        map_old2new = {}
        for gtf in GTF.iterator(options.stdin):
            ninput += 1
            key = gtf.transcript_id
            if key not in map_old2new:
                map_old2new[key] = options.unset_genes % (len(map_old2new) + 1)
            gtf.setAttribute( "gene_id",  map_old2new[key] )
            options.stdout.write( "%s\n" % str(gtf) )
            noutput += 1

    elif options.renumber_transcripts:
        
        map_old2new = {}
        for gtf in GTF.iterator(options.stdin):
            ninput += 1
            key = (gtf.gene_id, gtf.transcript_id)
            if key not in map_old2new:
                map_old2new[key] = options.renumber_transcripts % (len(map_old2new) + 1)
            gtf.setAttribute( "transcript_id",  map_old2new[key] )
            options.stdout.write( "%s\n" % str(gtf) )
            noutput += 1

    elif options.transcripts2genes:

        transcripts = set()
        genes = set()
        reset_strand = options.reset_strand
        for gtfs in GTF.iterator_transcripts2genes( GTF.iterator(options.stdin) ):

            ninput += 1
            for gtf in gtfs:
                if reset_strand: gtf.strand = "."
                options.stdout.write( "%s\n" % str(gtf) )                
                transcripts.add( gtf.transcript_id )
                genes.add( gtf.gene_id )
                nfeatures += 1
            noutput += 1

        if options.loglevel >= 1:
            options.stdlog.write("# transcripts2genes: transcripts=%i, genes=%i\n" % \
                                     (len(transcripts), len(genes)))

    elif options.rename:

        map_old2new = IOTools.readMap( open(options.filename_filter, "r") )

        if options.rename == "transcript":
            is_gene_id = False
        elif options.rename == "gene":
            is_gene_id = True
            
        for gff in GTF.iterator( options.stdin ):
            ninput += 1

            if is_gene_id:
                if gff.gene_id in map_old2new:
                    gff.setAttribute("gene_id", map_old2new[gff.gene_id])
                else:
                    E.debug( "removing missing gene_id %s" % gff.gene_id)
                    ndiscarded += 1
                    continue

            else:
                if gff.transcript_id in map_old2new:
                    gff.setAttribute("transcript_id", map_old2new[gff.transcript_id])
                else:
                    E.debug( "removing missing transcript_id %s" % gff.transcript_id)
                    ndiscarded += 1
                    continue

            noutput += 1
            options.stdout.write("%s\n" % str(gff))
                
    elif options.filter:

        keep_genes = set()
        if options.filter == "longest-gene":
            iterator = GTF.flat_gene_iterator( GTF.iterator(options.stdin) )
            coords = []
            gffs = []
            for gff in iterator:
                gff.sort( key = lambda x: x.start )
                coords.append( (gff[0].contig,
                                min([x.start for x in gff]), 
                                max([x.end for x in gff]),
                                gff[0].gene_id ) )
                gffs.append( gff )
            coords.sort()
            
            last_contig = None
            max_end = 0
            longest_gene_id = None
            longest_length = None

            for contig, start, end, gene_id in coords:
                ninput += 1
                if contig != last_contig or start >= max_end:
                    if longest_gene_id: keep_genes.add( longest_gene_id )
                    longest_gene_id = gene_id
                    longest_length = end - start
                    max_end = end
                else:
                    if end-start > longest_length:
                        longest_length, longest_gene_id = end-start, gene_id
                last_contig = contig
                max_end = max(max_end, end)

            keep_genes.add(longest_gene_id)
            invert = options.invert_filter
            for gff in gffs:
                keep = gff[0].gene_id in keep_genes

                if (keep and not invert) or (not keep and invert):
                    noutput += 1
                    for g in gff:
                        nfeatures += 1
                        options.stdout.write("%s\n" % g )
                else:
                    ndiscarded += 1

        elif options.filter in ("gene", "transcript"):
            if options.filename_filter:

                ids, nerrors = IOTools.ReadList( open(options.filename_filter, "r") )

                ids = set(ids)
                by_gene = options.filter == "gene"
                by_transcript = options.filter == "transcript"
                invert = options.invert_filter

                reset_strand = options.reset_strand
                for gff in GTF.iterator(options.stdin):

                    ninput += 1

                    keep = False
                    if by_gene: keep = gff.gene_id in ids
                    if by_transcript: keep = gff.transcript_id in ids
                    if (invert and keep) or (not invert and not keep): continue

                    if reset_strand: gff.strand = "."

                    options.stdout.write( "%s\n" % str(gff) )                
                    nfeatures += 1
                    noutput += 1

            elif options.sample_size:

                if options.filter == "gene":
                    iterator = GTF.flat_gene_iterator( GTF.iterator(options.stdin) )
                elif options.filter == "transcript":
                    iterator = GTF.transcript_iterator( GTF.iterator(options.stdin) )
                if options.min_exons_length:
                    iterator = GTF.iterator_min_feature_length( iterator, 
                                                                min_length = options.min_exons_length,
                                                                feature = "exon" )

                data = [ x for x in iterator ]
                ninput = len(data)
                if len(data) > options.sample_size:
                    data = random.sample( data, options.sample_size )

                for d in data:
                    noutput += 1
                    for dd in d:
                        nfeatures += 1
                        options.stdout.write( str(dd) + "\n" )

            else:
                assert False, "please supply either a filename with ids to filter with (--apply) or a sample-size."
        
    elif options.exons2introns:

        for gffs in GTF.flat_gene_iterator(GTF.iterator(options.stdin)):

            ninput += 1

            cds_ranges = GTF.asRanges( gffs, "CDS" )
            exon_ranges = GTF.asRanges( gffs, "exon" )
            input_ranges = Intervals.combine( cds_ranges + exon_ranges )
            
            if len(input_ranges) > 1:
                last = input_ranges[0][1]
                output_ranges = []
                for start, end in input_ranges[1:]:
                    output_ranges.append( (last, start) )
                    last = end

                for start, end in output_ranges:
                    
                    entry = GTF.Entry()
                    entry.copy( gffs[0] )
                    entry.clearAttributes()
                    entry.transcript_id = "merged"
                    entry.feature = "intron"
                    entry.start = start
                    entry.end = end
                    options.stdout.write( "%s\n" % str( entry ) )
                    nfeatures += 1                    
                noutput += 1
            else:
                ndiscarded += 1

    elif options.set_score2distance:

        for gffs in GTF.transcript_iterator(GTF.iterator(options.stdin)):
            ninput += 1
            strand = Genomics.convertStrand( gffs[0].strand )
            all_start, all_end = min( [ x.start for x in gffs ] ), max( [x.end for x in gffs ] ) 

            if strand != ".":
                t = 0            
                if strand == "-": gffs.reverse()
                for gff in gffs:
                    gff.score = t
                    t += gff.end - gff.start

                if strand == "-": gffs.reverse()
            for gff in gffs:
                options.stdout.write( "%s\n" % str( gff ) )
                nfeatures += 1
            noutput += 1

    elif options.remove_overlapping:
        
        index = GFF.readAndIndex( GFF.iterator( IOTools.openFile( options.remove_overlapping, "r" ) ) )
        
        for gffs in GTF.transcript_iterator(GTF.iterator(options.stdin)):
            ninput += 1
            found = False
            for e in gffs:
                if index.contains( e.contig, e.start, e.end ):
                    found = True
                    break
            
            if found:
                ndiscarded += 1    
            else:
                noutput += 1
                for e in gffs: 
                    nfeatures += 1
                    options.stdout.write( "%s\n" % str(e ) )

    elif options.intersect_transcripts:
        
        for gffs in GTF.gene_iterator(GTF.iterator(options.stdin), strict=options.strict ):
            
            ninput += 1
            r = []
            for g in gffs:
                if options.with_utr:
                    ranges = GTF.asRanges( g, "exon" )
                else:
                    ranges = GTF.asRanges( g, "CDS" )
                r.append( ranges )
                
            result = r[0]
            for r in r[1:]:
                result = Intervals.intersect( result, r )
            
            entry = GTF.Entry()
            entry.copy( gffs[0][0] )
            entry.clearAttributes()
            entry.transcript_id = "merged"
            entry.feature = "exon"
            for start, end in result:
                entry.start = start
                entry.end = end
                options.stdout.write( "%s\n" % str( entry ) )
                nfeatures += 1
                
            noutput += 1
    else:
        for gffs in GTF.flat_gene_iterator(GTF.iterator(options.stdin), strict=options.strict ):

            ninput += 1

            cds_ranges = GTF.asRanges( gffs, "CDS" )
            exon_ranges = GTF.asRanges( gffs, "exon" )

            # sanity checks
            strands = set( [x.strand for x in gffs ] )
            contigs = set( [x.contig for x in gffs ] )
            if len(strands) > 1:
                raise ValueError( "can not merge gene '%s' on multiple strands: %s" % (gffs[0].gene_id, str(strands)))

            if len(contigs) > 1:
                raise ValueError( "can not merge gene '%s' on multiple contigs: %s" % (gffs[0].gene_id, str(contigs)))

            strand = Genomics.convertStrand( gffs[0].strand )

            if cds_ranges and options.with_utr:
                cds_start, cds_end = cds_ranges[0][0], cds_ranges[-1][1]
                midpoint = ( cds_end - cds_start ) / 2 + cds_start

                utr_ranges = []
                for start, end in Intervals.truncate( exon_ranges, cds_ranges ):
                    if end - start > 3:
                        if strand == ".":
                            feature = "UTR"
                        elif strand == "+":
                            if start < midpoint:
                                feature = "UTR5"
                            else:
                                feature = "UTR3"
                        elif strand == "-":
                            if start < midpoint:
                                feature = "UTR3"
                            else:
                                feature = "UTR5"
                        utr_ranges.append( (feature, start,end) )
                output_feature = "CDS"
                output_ranges = cds_ranges
            else:
                output_feature = "exon"
                output_ranges = exon_ranges
                utr_ranges = []

            result = []

            if options.merge_exons:

                # need to combine per feature - skip
                # utr_ranges = Intervals.combineAtDistance( utr_ranges, options.merge_exons_distance )

                output_ranges = Intervals.combineAtDistance( output_ranges, options.merge_exons_distance )

                for feature, start, end in utr_ranges:
                    entry = GTF.Entry()
                    entry.copy( gffs[0] )
                    entry.clearAttributes()
                    entry.feature = feature
                    entry.transcript_id = "merged"
                    entry.start = start
                    entry.end = end
                    result.append( entry )

                for start, end in output_ranges:

                    entry = GTF.Entry()
                    entry.copy( gffs[0] )
                    entry.clearAttributes()
                    entry.transcript_id = "merged"
                    entry.feature = output_feature
                    entry.start = start
                    entry.end = end
                    result.append( entry )

            elif options.merge_transcripts:

                entry = GTF.Entry()
                entry.copy( gffs[0] )
                entry.clearAttributes()
                entry.transcript_id = entry.gene_id
                entry.start = output_ranges[0][0]
                entry.end = output_ranges[-1][1]
                result.append( entry )

            elif options.merge_introns:

                if len( output_ranges ) >= 2:
                    entry = GTF.Entry()
                    entry.copy( gffs[0] )
                    entry.clearAttributes()
                    entry.transcript_id = entry.gene_id
                    entry.start = output_ranges[0][1]
                    entry.end = output_ranges[-1][0]
                    result.append( entry )
                else:
                    ndiscarded += 1
                    continue

            result.sort( key=lambda x: x.start )

            for x in result:
                options.stdout.write( "%s\n" % str(x) )
                nfeatures += 1
            noutput += 1

    E.info("ninput=%i, noutput=%i, nfeatures=%i, ndiscarded=%i" % (ninput, noutput, nfeatures, ndiscarded) )
    E.Stop()
