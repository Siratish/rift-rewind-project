"""
League of Legends Match History ETL Pipeline.

This script processes match history data for a given player (PUUID) and year,
transforming it into aggregated statistics and summaries stored in S3.
"""

import argparse
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import boto3
import requests
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import (
    col, explode, sum as _sum, avg, max as _max, min as _min, count as _count,
    when, collect_list, from_unixtime, to_timestamp,
    month, hour, dayofweek, lag, udf, desc, row_number, struct, array
)
from pyspark.sql.window import Window
from pyspark.sql.types import StringType

# Get environment variables
import os

S3_BUCKET = os.environ['S3_BUCKET']


def fetch_ddragon_data(url):
    return requests.get(url).json()


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Process LoL match history data")
    parser.add_argument("--puuid", required=True, help="Player's PUUID")
    parser.add_argument("--year", type=int, default=2024,
                        help="Year to process")
    return parser.parse_known_args()


def initialize_spark() -> SparkSession:
    """Initialize and return a Spark session."""
    return SparkSession.builder.appName("RiotMatchETL").getOrCreate()


def fetch_ddragon_data(url: str) -> Dict:
    """Fetch data from Riot's Data Dragon API."""
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise Exception(f"Failed to fetch Data Dragon data: {e}")


def load_game_data(year: int) -> Dict:
    """Load game data from Data Dragon."""
    base_version = f"{year-2010}"
    latest_patch = f"{base_version}.24.1"
    first_patch = f"{base_version}.1.1"

    # Load item data from both patches
    item_data_latest = fetch_ddragon_data(
        f"https://ddragon.leagueoflegends.com/cdn/{latest_patch}/data/en_US/item.json"
    )["data"]
    item_data_old = fetch_ddragon_data(
        f"https://ddragon.leagueoflegends.com/cdn/{first_patch}/data/en_US/item.json"
    )["data"]

    # Load spell and rune data
    spell_data = fetch_ddragon_data(
        f"https://ddragon.leagueoflegends.com/cdn/{latest_patch}/data/en_US/summoner.json"
    )["data"]
    rune_data = fetch_ddragon_data(
        f"https://ddragon.leagueoflegends.com/cdn/{latest_patch}/data/en_US/runesReforged.json"
    )
    
    queues = fetch_ddragon_data(
        "https://static.developer.riotgames.com/docs/lol/queues.json"
    )
    
    queue_map = {}
    for q in queues:
        qid = q.get("queueId")
        map_name = q.get("map")
        desc = q.get("description")
        notes = q.get("notes")
    
        if desc is None and notes is None:
            formatted = f"{map_name}"
        elif desc is not None and notes is None:
            formatted = f"{map_name}: {desc}"
        elif desc is None and notes is not None:
            formatted = f"{map_name} ({notes})"
        else:
            formatted = f"{map_name}: {desc} ({notes})"
    
        queue_map[qid] = formatted

    return {
        "items": {
            "latest": {int(k): v["name"] for k, v in item_data_latest.items()},
            "old": {int(k): v["name"] for k, v in item_data_old.items()}
        },
        "spells": {int(v["key"]): v["name"] for v in spell_data.values()},
        "runes": {style["id"]: style["name"] for style in rune_data},
        "modes": queue_map
    }


def create_mapping_udfs(game_data: Dict) -> Dict:
    """Create UDFs for mapping game data IDs to names."""
    def map_item(item_id: int) -> str:
        return (game_data["items"]["latest"].get(int(item_id)) or
                game_data["items"]["old"].get(int(item_id)) or
                str(item_id))

    def map_rune(rune_id: int) -> str:
        return game_data["runes"].get(int(rune_id), str(rune_id))

    def map_spell(spell_id: int) -> str:
        return game_data["spells"].get(int(spell_id), str(spell_id))
        
    def map_mode(queue_id: int) -> str:
        return game_data["modes"].get(int(queue_id), str(queue_id))

    return {
        "item": udf(map_item, StringType()),
        "rune": udf(map_rune, StringType()),
        "spell": udf(map_spell, StringType()),
        "mode": udf(map_mode, StringType())
    }


def process_match_data(df: DataFrame, mapping_udfs: Dict) -> DataFrame:
    """Process raw match data with feature engineering."""
    return (df
            .withColumn("gameDate", to_timestamp(from_unixtime(col("gameCreation") / 1000)))
            .withColumn("month", month("gameDate"))
            .withColumn("hour", hour("gameDate"))
            .withColumn("dayOfWeek", dayofweek("gameDate"))
            .withColumn("csPerMin",
                        (col("totalMinionsKilled") + col("neutralMinionsKilled")) /
                        (col("gameDuration") / 60))
            .withColumn("kda",
                        (col("kills") + col("assists")) /
                        when(col("deaths") == 0, 1).otherwise(col("deaths")))
            .withColumn("dmgPerMin",
                        col("totalDamageDealtToChampions") / (col("gameDuration") / 60))
            .withColumn("dmgTakenPerMin",
                        col("totalDamageTaken") / (col("gameDuration") / 60))
            .withColumn("hoursPlayed", col("gameDuration") / 3600)
            .withColumn("gameMode", mapping_udfs["mode"](col("queueId"))))


def create_champion_summary(df: DataFrame, mapping_udfs: Dict) -> DataFrame:
    """Create champion-level summary statistics."""
    window_best_kda = Window.partitionBy(
        "championName", "gameMode").orderBy(desc("kda"))

    # Find best games per champion
    best_games = (df
                  .withColumn("rank", row_number().over(window_best_kda))
                  .filter(col("rank") == 1)
                  .select(
                      "championName",
                      "kills", "deaths", "assists", "kda", "win",
                      "gameDate", "gameMode",
                      col("perks.primaryStyle").alias("primaryRuneId"),
                      col("perks.subStyle").alias("secondaryRuneId"),
                      col("summoner1Id").alias("spell1Id"),
                      col("summoner2Id").alias("spell2Id")
                  )
                  .withColumn("primaryRune", mapping_udfs["rune"](col("primaryRuneId")))
                  .withColumn("secondaryRune", mapping_udfs["rune"](col("secondaryRuneId")))
                  .withColumn("summonerSpell1", mapping_udfs["spell"](col("spell1Id")))
                  .withColumn("summonerSpell2", mapping_udfs["spell"](col("spell2Id"))))

    # Aggregate champion statistics
    champ_stats = df.groupBy("championName", "gameMode").agg(
        _count("*").alias("gamesPlayed"),
        avg(when(col("win") == True, 1).otherwise(0)).alias("winRate"),
        avg("kda").alias("avgKDA"),
        avg("csPerMin").alias("avgCSperMin")
    )

    # Combine statistics with best games
    return (champ_stats
            .join(best_games, on=["championName", "gameMode"], how="left")
            .select(
                "championName",
                "gameMode",
                "gamesPlayed",
                "winRate",
                "avgKDA",
                "avgCSperMin",
                struct(
                    "kills", "deaths", "assists", "kda", "win",
                    "gameDate", "gameMode", "primaryRune", "secondaryRune",
                    array("summonerSpell1", "summonerSpell2").alias(
                        "summonerSpells")
                ).alias("bestGame")
            ))


def create_item_summary(df: DataFrame, mapping_udfs: Dict) -> DataFrame:
    """Create item-level summary statistics."""
    items = (df
             .select(
                 "gameMode",
                 explode("items").alias("itemId"),
                 "win", "kda", "goldEarned", "visionScore",
                 "dmgPerMin", "dmgTakenPerMin"
             )
             .filter(col("itemId") != 0))

    # Calculate item statistics by game mode
    item_stats = (items
                  .groupBy("itemId", "gameMode")
                  .agg(
                      _count("*").alias("usageCount"),
                      avg(when(col("win") == True, 1).otherwise(
                          0)).alias("winRate"),
                      avg("kda").alias("avgKDA"),
                      avg("goldEarned").alias("avgGoldEarned"),
                      avg("visionScore").alias("avgVisionScore"),
                      avg("dmgPerMin").alias("avgDamagePerMin"),
                      avg("dmgTakenPerMin").alias("avgDamageTakenPerMin")
                  )
                  .withColumn("itemName", mapping_udfs["item"](col("itemId"))))

    # Group statistics by item
    return (item_stats
            .groupBy("itemName")
            .agg(collect_list(
                struct(
                    "gameMode", "usageCount", "winRate", "avgKDA",
                    "avgGoldEarned", "avgVisionScore", "avgDamagePerMin",
                    "avgDamageTakenPerMin"
                )
            ).alias("modes")))


def create_spell_summary(df: DataFrame, mapping_udfs: Dict) -> DataFrame:
    """Create summoner spell combo summary statistics."""
    spells = df.select(
        "gameMode", "championName",
        col("summoner1Id").alias("spell1Id"),
        col("summoner2Id").alias("spell2Id"),
        "win", "kda"
    )

    # Calculate base performance metrics
    spell_stats = (spells
                   .groupBy("spell1Id", "spell2Id", "gameMode")
                   .agg(
                       _count("*").alias("comboCount"),
                       avg(when(col("win") == True, 1).otherwise(
                           0)).alias("winRate"),
                       avg("kda").alias("avgKDA")
                   ))

    # Find top champions for each spell combo
    champ_usage = (spells
                   .groupBy("spell1Id", "spell2Id", "gameMode", "championName")
                   .agg(_count("*").alias("gamesPlayed"))
                   .withColumn(
                       "rank",
                       row_number().over(
                           Window.partitionBy(
                               "spell1Id", "spell2Id", "gameMode")
                           .orderBy(desc("gamesPlayed"))
                       )
                   )
                   .filter(col("rank") <= 5)
                   .groupBy("spell1Id", "spell2Id", "gameMode")
                   .agg(collect_list(
                       struct("championName", "gamesPlayed")
                   ).alias("champions")))

    # Combine stats and map IDs to names
    return (spell_stats
            .join(champ_usage, on=["spell1Id", "spell2Id", "gameMode"], how="left")
            .withColumn("spell1Name", mapping_udfs["spell"](col("spell1Id")))
            .withColumn("spell2Name", mapping_udfs["spell"](col("spell2Id")))
            .groupBy("spell1Name", "spell2Name")
            .agg(collect_list(
                struct(
                    "gameMode", "comboCount", "winRate",
                    "avgKDA", "champions"
                )
            ).alias("modes")))


def create_rune_summary(df: DataFrame, mapping_udfs: Dict) -> DataFrame:
    """Create rune style combo summary statistics."""
    runes = df.select(
        "gameMode", "championName",
        col("perks.primaryStyle").alias("primaryStyleId"),
        col("perks.subStyle").alias("subStyleId"),
        "win", "kda"
    )

    # Calculate base performance metrics
    rune_stats = (runes
                  .groupBy("primaryStyleId", "subStyleId", "gameMode")
                  .agg(
                      _count("*").alias("comboCount"),
                      avg(when(col("win") == True, 1).otherwise(
                          0)).alias("winRate"),
                      avg("kda").alias("avgKDA")
                  ))

    # Find top champions for each rune combo
    champ_usage = (runes
                   .groupBy("primaryStyleId", "subStyleId", "gameMode", "championName")
                   .agg(_count("*").alias("gamesPlayed"))
                   .withColumn(
                       "rank",
                       row_number().over(
                           Window.partitionBy(
                               "primaryStyleId", "subStyleId", "gameMode")
                           .orderBy(desc("gamesPlayed"))
                       )
                   )
                   .filter(col("rank") <= 5)
                   .groupBy("primaryStyleId", "subStyleId", "gameMode")
                   .agg(collect_list(
                       struct("championName", "gamesPlayed")
                   ).alias("champions")))

    # Combine stats and map IDs to names
    return (rune_stats
            .join(champ_usage, on=["primaryStyleId", "subStyleId", "gameMode"], how="left")
            .withColumn("primaryStyle", mapping_udfs["rune"](col("primaryStyleId")))
            .withColumn("subStyle", mapping_udfs["rune"](col("subStyleId")))
            .groupBy("primaryStyle", "subStyle")
            .agg(collect_list(
                struct(
                    "gameMode", "comboCount", "winRate",
                    "avgKDA", "champions"
                )
            ).alias("modes")))


def create_role_summary(df: DataFrame) -> DataFrame:
    """Create role-based summary statistics."""
    return (df
            .groupBy("teamPosition", "gameMode")
            .agg(
                _count("*").alias("gamesPlayed"),
                avg(when(col("win") == True, 1).otherwise(0)).alias("winRate"),
                avg("kda").alias("avgKDA")
            )
            .groupBy("teamPosition")
            .agg(collect_list(
                struct(
                    "gameMode", "gamesPlayed", "winRate", "avgKDA"
                )
            ).alias("modes")))


def create_time_summaries(df: DataFrame) -> tuple:
    """Create time-based summary statistics."""
    # Hourly summary
    hour_summary = (df
                    .groupBy("hour", "gameMode")
                    .agg(_count("*").alias("gamesPlayed"))
                    .groupBy("hour")
                    .agg(collect_list(
                        struct("gameMode", "gamesPlayed")
                    ).alias("modes")))

    # Monthly summary
    month_summary = (df
                     .groupBy("month", "gameMode")
                     .agg(_count("*").alias("gamesPlayed"))
                     .groupBy("month")
                     .agg(collect_list(
                         struct("gameMode", "gamesPlayed")
                     ).alias("modes")))

    return hour_summary, month_summary


def analyze_streaks(df: DataFrame) -> Tuple[Dict, Dict]:
    """Analyze win/lose streaks."""
    window_spec = Window.orderBy("gameDate")

    streak_df = (df
                 .withColumn("prevWin", lag("win", 1).over(window_spec))
                 .withColumn(
                     "streakChange",
                     when(col("win") != col("prevWin"), 1).otherwise(0)
                 )
                 .withColumn("streakGroup", _sum("streakChange").over(window_spec)))

    streaks = (streak_df
               .groupBy("streakGroup")
               .agg(
                   _count("*").alias("streakLength"),
                   _max("win").alias("isWinStreak"),
                   _min("gameDate").alias("startDate"),
                   _max("gameDate").alias("endDate")
               ))

    # Find longest win streak
    win_streak = (streaks
                  .filter(col("isWinStreak") == True)
                  .orderBy(desc("streakLength"))
                  .limit(1)
                  .collect())

    # Find longest lose streak
    lose_streak = (streaks
                   .filter(col("isWinStreak") == False)
                   .orderBy(desc("streakLength"))
                   .limit(1)
                   .collect())

    def format_streak(streak_row: List) -> Dict:
        if not streak_row:
            return {"length": 0, "startDate": None, "endDate": None}
        return {
            "length": streak_row[0]["streakLength"],
            "startDate": streak_row[0]["startDate"],
            "endDate": streak_row[0]["endDate"]
        }

    return format_streak(win_streak), format_streak(lose_streak)


def create_global_summary(df: DataFrame) -> Dict:
    """Create global summary statistics."""
    # Overall statistics
    global_stats = df.agg(
        _count("*").alias("totalGames"),
        _sum(when(col("win") == True, 1).otherwise(0)).alias("totalWins"),
        _sum("hoursPlayed").alias("totalHoursPlayed")
    ).withColumn("winRate", col("totalWins") / col("totalGames"))

    # Per-mode statistics
    mode_stats = df.groupBy("gameMode").agg(
        _count("*").alias("gamesPlayed"),
        avg(when(col("win") == True, 1).otherwise(0)).alias("winRate"),
        avg("kda").alias("avgKDA"),
        avg("csPerMin").alias("avgCSperMin"),
        avg("dmgPerMin").alias("avgDamagePerMin"),
        avg("dmgTakenPerMin").alias("avgDamageTakenPerMin"),
        avg("gameDuration").alias("avgGameDuration"),
        _max("goldEarned").alias("highestGold"),
        _max("visionScore").alias("highestVision")
    )

    global_data = global_stats.toPandas().to_dict(orient="records")[0]
    global_data["modes"] = mode_stats.toPandas().to_dict(orient="records")

    return global_data


def save_to_s3(data: Dict, puuid: str, year: int, bucket: str, prefix: str) -> None:
    """Save processed data and metadata to S3."""
    s3 = boto3.client("s3")

    class DateTimeEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)

    data_key = f"{prefix}/final_summary_{year}.json"
    metadata_key = f"{data_key}.metadata.json"

    try:
        # Save data file
        s3.put_object(
            Bucket=bucket,
            Key=data_key,
            Body=json.dumps(data, cls=DateTimeEncoder),
            ContentType="application/json"
        )
        
        # Save metadata file
        metadata = {
            "metadataAttributes": {
                "puuid": puuid,
                "year": year
            }
        }
        s3.put_object(
            Bucket=bucket,
            Key=metadata_key,
            Body=json.dumps(metadata),
            ContentType="application/json"
        )
        
        print(f"✅ Player summary and metadata written to s3://{bucket}/{data_key}[.metadata.json]")
    except Exception as e:
        raise Exception(f"Failed to save data to S3: {e}")

def main():
    """Main ETL pipeline."""
    args, _ = parse_arguments()

    # Configure paths - use environment variable for bucket
    s3_input = f"s3://{S3_BUCKET}/match-history/{args.puuid}/stats/{args.year}/"
    s3_output_prefix = f"summary/{args.puuid}"

    # Initialize Spark and load game data
    spark = initialize_spark()
    game_data = load_game_data(args.year)
    mapping_udfs = create_mapping_udfs(game_data)

    try:
        # Read and process match data
        df = spark.read.option("recursiveFileLookup", "true").option(
            "multiLine", "true").json(s3_input)
        processed_df = process_match_data(df, mapping_udfs)

        # Generate summaries
        champ_summary = create_champion_summary(processed_df, mapping_udfs)
        item_summary = create_item_summary(processed_df, mapping_udfs)
        spell_summary = create_spell_summary(processed_df, mapping_udfs)
        rune_summary = create_rune_summary(processed_df, mapping_udfs)
        role_summary = create_role_summary(processed_df)
        time_summary, month_summary = create_time_summaries(processed_df)
        win_streak, lose_streak = analyze_streaks(processed_df)
        global_summary = create_global_summary(processed_df)

        # Add streak information
        global_summary["longestWinStreak"] = win_streak
        global_summary["longestLoseStreak"] = lose_streak

        # Combine all summaries
        final_data = {
            "playerPUUID": args.puuid,
            "summary": {
                "global": global_summary,
                "champions": champ_summary.toPandas().to_dict(orient="records"),
                "roles": role_summary.toPandas().to_dict(orient="records"),
                "items": item_summary.toPandas().to_dict(orient="records"),
                "spells": spell_summary.toPandas().to_dict(orient="records"),
                "runes": rune_summary.toPandas().to_dict(orient="records"),
                "activityByHour": time_summary.toPandas().to_dict(orient="records"),
                "activityByMonth": month_summary.toPandas().to_dict(orient="records")
            }
        }

        # Save results
        save_to_s3(final_data, args.puuid, args.year,
                   S3_BUCKET, s3_output_prefix)

    except Exception as e:
        print(f"❌ Error processing match data: {e}")
        raise


if __name__ == "__main__":
    main()
