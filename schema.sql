/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;

CREATE TABLE IF NOT EXISTS `gpm_albums` (
  `albumid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `gpm_albumid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `album_purchaseable` tinyint(1) unsigned DEFAULT NULL,
  `album` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `album_artist` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`albumid`),
  UNIQUE KEY `gpm_albumid` (`gpm_albumid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `gpm_album_art` (
  `album_artid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `deleted` tinyint(1) unsigned NOT NULL DEFAULT '0',
  `albumid` int(10) unsigned NOT NULL,
  `aspect_ratio` tinyint(3) unsigned NOT NULL,
  `autogen` tinyint(1) unsigned NOT NULL,
  `kind` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `url` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`album_artid`),
  UNIQUE KEY `albumid_aspect_ratio_url` (`albumid`,`aspect_ratio`,`url`),
  KEY `albumid` (`albumid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `gpm_artists` (
  `artistid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `gpm_artistid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `artist` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`artistid`),
  UNIQUE KEY `gpm_artistid` (`gpm_artistid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `gpm_artist_art` (
  `artist_artid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `deleted` tinyint(1) unsigned NOT NULL DEFAULT '0',
  `artistid` int(10) unsigned NOT NULL,
  `aspect_ratio` tinyint(3) unsigned NOT NULL,
  `autogen` tinyint(1) unsigned NOT NULL,
  `kind` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `url` varchar(512) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`artist_artid`),
  UNIQUE KEY `artistid_ratio_url` (`artistid`,`aspect_ratio`,`url`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci ROW_FORMAT=DYNAMIC;

CREATE TABLE IF NOT EXISTS `gpm_playlists` (
  `playlistid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `gpm_playlistid` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dt_created` datetime NOT NULL,
  `dt_modified` datetime DEFAULT NULL,
  `deleted` tinyint(1) unsigned NOT NULL DEFAULT '0',
  `dt_recent` datetime DEFAULT NULL,
  `access_controlled` tinyint(1) unsigned DEFAULT NULL,
  `kind` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `owner_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `share_token` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`playlistid`),
  UNIQUE KEY `gpm_playlistid` (`gpm_playlistid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `gpm_playlist_entries` (
  `entryid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `gpm_entryid` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `dt_created` datetime NOT NULL,
  `dt_modified` datetime DEFAULT NULL,
  `deleted` tinyint(1) unsigned NOT NULL DEFAULT '0',
  `dt_deleted` datetime DEFAULT NULL,
  `absolute_position` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '0',
  `clientid` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '0',
  `kind` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '0',
  `gpm_playlistid` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT '0',
  `source` tinyint(1) unsigned DEFAULT NULL,
  `gpm_trackid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `processed` tinyint(1) unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`entryid`),
  UNIQUE KEY `gpm_entryid` (`gpm_entryid`),
  KEY `gpm_trackid` (`gpm_trackid`),
  KEY `processed` (`processed`),
  KEY `gpm_playlistid` (`gpm_playlistid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `gpm_tracks` (
  `trackid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `gpm_trackid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `gpm_albumid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `artist` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `composer` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `disc_number` int(11) unsigned DEFAULT NULL,
  `duration_millis` int(11) unsigned DEFAULT NULL,
  `est_size` bigint(20) unsigned DEFAULT NULL,
  `explicit_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `genre` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `kind` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `nid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `play_count` int(11) unsigned DEFAULT NULL,
  `rating` tinyint(3) unsigned DEFAULT NULL,
  `storeid` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `title` varchar(512) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `track_purchaseable` tinyint(1) unsigned DEFAULT NULL,
  `track_subscribable` tinyint(1) unsigned DEFAULT NULL,
  `track_num` int(11) unsigned DEFAULT NULL,
  `track_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `year` year(4) DEFAULT NULL,
  PRIMARY KEY (`trackid`),
  UNIQUE KEY `gpm_trackid` (`gpm_trackid`),
  KEY `gpm_albumid` (`gpm_albumid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `gpm_track_artists` (
  `linkid` int(10) unsigned NOT NULL AUTO_INCREMENT,
  `trackid` int(10) unsigned NOT NULL,
  `albumid` int(10) unsigned NOT NULL,
  `artistid` int(10) unsigned NOT NULL,
  PRIMARY KEY (`linkid`),
  UNIQUE KEY `trackid_albumid_artistid` (`trackid`,`albumid`,`artistid`),
  KEY `artistid` (`artistid`),
  KEY `albumid` (`albumid`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IF(@OLD_FOREIGN_KEY_CHECKS IS NULL, 1, @OLD_FOREIGN_KEY_CHECKS) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
