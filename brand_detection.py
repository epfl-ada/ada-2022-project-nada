
import pandas as pd
import re
import numpy as np
from functools import partial
import multiprocess as mp
from itertools import permutations
import tqdm as tqdm
import argparse

# LOAD_FILE = 'science_and_technology_videos.csv'
# SAVE_FILE = 'c.csv'
VIDEOS_METADATA_COLUMNS = ["categories", "channel_id", 
                           "crawl_date", "description", 
                           "dislike_count", "display_id", 
                           "duration", "like_count", "tags", 
                           "title", "upload_date", "view_count"]
# SMARTPHONES_DATA = "data/Phone_to_Smartphone.csv"
BRANDS_TO_ANALYZE = ["Samsung", "Apple" , "Huawei", "Xiaomi", "Oppo", ]
MONTHS_NAMES = ["January", "February", "March", 
                "April", "May", "June", "July", 
                "August", "September", "October", 
                "November", "December"]


def capture_year(string):
    """
    Returns the Year by matching the string with a regular Expression.
    
    Arguments:
        string (string): Any string that might or might not contain 4 consecutive numbers representing year
        
    returns:
        int: 4 digit integer representing the year.
    """
    year = re.search('([0-9]{4})',string)
    if year:
        return int(year.group(0))
    else:
        return -1
    
def get_brand_models(brand_name, df):
    """
    Returns a subset of the original dataframe corresponding
    only to the videos that mention the given brand.
    
    arguments:
            brand_name (string) : the name of the brand the 
                video retrieved should mention
            df (pandas.DataFrame) : a preprocessed dataframe
                containing as rows the videos as well as their
                associated brands
    returns:
            A dataframe containing only the videos the mention
            the brand passes as parameter
    """
    return df[df.Brand == brand_name].Name.unique()

def calc_release(row, months):
    """
    This function parses the string containing a date in ambiguous format. 
    It tries to parse it using regular expressions and returns a date with the most precision it can get.
    
    arguments:
            row (pandas.Series) : a row of the dataset that contain
                    the metadata realted to a video.
            months (List) : A list containing anmes of the 12 months
            
    returns:
            pandas.DateTime : DateTime object containing the date
    """

    year = row.released_year
    release = re.sub(r"\s*Released\s*", "", row.released_at, flags=re.IGNORECASE)
    
    full_date = re.search(r"[0-9]{4}, [a-z]+\s[0-9]{2}", release, flags=re.IGNORECASE)
    quarters_date = re.search(r"[0-9]{4}, [A-Z][1-4]", release, flags=re.IGNORECASE)
    months_date = re.search(r"[0-9]{4}, [A-Za-z]+", release, flags=re.IGNORECASE) #[A-Za-z]:match any single uppercase or lowercase letter.
    years_date = re.search(r"[0-9]{4}", release)
    
    if full_date:
        return pd.to_datetime(full_date.group(0))
    elif quarters_date:
        q = int(quarters_date.group(0)[-1])
        m = months[(q-1)*3 + 1]
        return pd.to_datetime("{}/{}".format(m, year))
    elif months_date:
        str_month_date = months_date.group(0)
        year, month = str_month_date.split(",")
        # remove white space
        month = month.strip()
        # lower case the month to compare with the lower case of all possible months
        month = month.lower()
        if month in str(MONTHS_NAMES).lower():   
            return pd.to_datetime(months_date.group(0))
    elif years_date:
        return pd.to_datetime(years_date.group(0))
    else:
        return None
    
def find_brand(brand_models, row):
    """
    Returns a list containing all of the brands, among the ones
    contained in brand_models.keys(), which have at least one 
    model that is mentioned in the textual fields of the given
    video. The textual fields searched are the title, the 
    description and the tags of the video.
    
    arguments:
            row (pandas.Series) : a row of the dataset that contain
                    the metadata realted to a video.
            brand_models (dict) : a dictionary containing as keys
                    the brands names and as values a list containing
                    all the models released by this brand.
    returns : 
            A list containing the brands that matched according 
            to the brand_models dictionary
    """
    brands_mentioned = []
    for brand in brand_models.keys():
        for model in brand_models[brand]:
            model = model.lower()
            if (model in row.title.lower()
                or (model in row.description.lower())
                or model in row.tags.lower()):
                brands_mentioned.append(brand)
                break
    if len(brands_mentioned) == 0:
        return None
    return brands_mentioned

def brands_seperated(brand_models, row):
    brands_detected = {'title' : set(),
                       'description' : set(),
                       'tags' : set()}
    brands_title_description = []
    brands_tags = []
    for brand in brand_models.keys():
        for model in brand_models[brand]:
            model = model.lower()
            if model in row.title.lower() :
                brands_detected['title'].add(brand)
            if model in row.description.lower() :
                brands_detected['description'].add(brand)
            if model in row.tags.lower() :
                brands_detected['tags'].add(brand)
    if (len(brands_detected['title']) == 0 
    and len(brands_detected['description']) == 0
    and len(brands_detected['tags']) == 0):
        return None
    return brands_detected

def brands_seperated_tuple(brand_models, row):
    brands_detected = [set(), set(), set(), set()] # [title_brands, description_brands, tags_brands, union]
    brands_title_description = []
    brands_tags = []
    for brand in brand_models.keys():
        for model in brand_models[brand]:
            model = model.lower()
            if model in row.title.lower() :
                brands_detected[0].add(brand)
            if model in row.description.lower() :
                brands_detected[1].add(brand)
            if model in row.tags.lower() :
                brands_detected[2].add(brand)
    if (len(brands_detected[0]) == 0 
    and len(brands_detected[1]) == 0
    and len(brands_detected[2]) == 0):
        return [None, None, None, None]

    brands_detected[3] = brands_detected[0].union(brands_detected[1], brands_detected[2])
    return brands_detected


def main(args):
    print("Loading Smartphone Data")
    phone_models_df = pd.read_csv(args.smartphones_data)
    phone_models_df["released_year"] = phone_models_df.released_at.apply(lambda x : capture_year(str(x)))
    phone_models_df.drop(phone_models_df[phone_models_df["released_year"] == -1].index, axis=0, inplace=True)
    phone_models_df["release"] = phone_models_df.apply(lambda x : calc_release(x, MONTHS_NAMES), axis=1)
    phone_models_df = phone_models_df.set_index("release")
    filtered_phones = phone_models_df[(phone_models_df["released_year"] > 2004) & (phone_models_df["released_year"] < 2020)]


    brand_models = dict()
    for brand in BRANDS_TO_ANALYZE:
        brand_models[brand] = get_brand_models(brand, filtered_phones)

    print("Creating Keywords")
    model_keywords = {}
    #test_brand_models = brand_models.copy()
    #define a list with all irrelevant words that must be removed in a model name
    TO_REMOVE_WORD_LOWER = ["(", ")" , "." , "wi-fi",  "+" , "cellular","lte","cdma","4g","3g"]
    #define a list with all irrelevant words that are not associated with smartphones 
    TO_REMOVE_MODEL_PAD_LOWER = ["ipad","pad","tab","tv"]
    for brand in BRANDS_TO_ANALYZE:  
        model_keywords_temp = []

        for model in brand_models[brand]: 
            PAD = False
            mod_words = model.split(' ')
            model_words = mod_words.copy()
            for word in mod_words:
                lower_word = word.lower() 
                if any(substring in lower_word for substring in TO_REMOVE_MODEL_PAD_LOWER):
                    PAD = True
                if any(substring in lower_word for substring in TO_REMOVE_WORD_LOWER):
                    model_words.remove(word)
            if not PAD: # not a tablet
                model_name  = ' '.join(model_words)
                model_keywords_temp.append(model_name)
                #add all the combinations with (len(model_words)-1) words
                if len(model_words) > 2:
                    permuted_models = permutations(model_words, (len(model_words)-1))
                    list_permuted_models = set(permuted_models)
                    for perm in list_permuted_models:
                        model_keywords_temp.append(' '.join(perm))
                    
        brand_models[brand] = model_keywords_temp

    # load  and clean dataset
    print("Loading Videos Metadata")
    df = pd.read_csv(args.load_file, names=VIDEOS_METADATA_COLUMNS, nrows=args.num_rows, skiprows=args.skip_rows)
    df.tags.replace(np.nan, "", inplace=True)
    df.description.replace(np.nan, "", inplace=True)
    print(f"length : {len(df)}")

    # print("Creating Sample")
    # df_sample = df.sample(1000)
    # df_sample['brands_seperated'] = df_sample.apply(lambda x : brands_seperated(brand_models, x), axis=1)

    find_brand_p = partial(brands_seperated_tuple, brand_models)

    def apply_on_chunk(dff: pd.DataFrame):
        return dff.apply(find_brand_p, axis=1, result_type='expand')    

    #apply_on_chunk_p = partial(apply_on_chunk, func=find_brand_p, axis=1)


    # NUM_PROCESSES = 20      # Should be equal to no. of cores (or double)
    # NUM_CHUNKS = 1000       # Should be such that chunk size is not very high.

    print("Running in parallel")
    with mp.Pool(processes=args.num_processes) as pool:
        r = list(tqdm.tqdm(pool.imap(apply_on_chunk, np.array_split(df, args.num_chunks_parallel)), total=args.num_chunks_parallel))
        print("Concatenating Chunks")
        new_cols = pd.concat(r)
        print("Concatenating Results")
        df = pd.concat([df, new_cols], axis='columns')
        df = df.rename(columns={0 : 'title_brands', 1 : 'description_brands', 2 : 'tags_brands', 3 : 'union'})

    print("Saving to file")
    df.to_csv(args.save_file, compression="gzip")


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--load_file', type=str, default='science_and_technology_videos.csv')
    parser.add_argument('--save_file', type=str, default='videos_with_brands.csv')
    parser.add_argument('--smartphones_data', type=str, default='Phone_to_Smartphone.csv')
    parser.add_argument('--num_processes', type=int, default=40)
    parser.add_argument('--num_chunks_parallel', type=int, default=100)
    parser.add_argument('--num_rows', type=int, default=1000000)
    parser.add_argument('--skip_rows', type=int, default=0)
    return parser.parse_args()

if __name__ == '__main__':

    args = parse_args()
    main(args)