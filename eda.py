import pandas as pd
import numpy as np
from sklearn.impute import KNNImputer
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv
load_dotenv()

def load_and_preprocess_mobile_data(file_path: str) -> pd.DataFrame:
    """
    Loads the mobile data, cleans column names, handles duplicates,
    converts price to numeric, removes outliers, and converts object columns to categories.
    """
    mobile_df = pd.read_csv(file_path)

    # Convert all column names to lowercase
    mobile_df.columns = [col.lower() for col in mobile_df.columns]

    # Convert all entire rows to lowercase for object type columns
    for col in mobile_df.select_dtypes(include=['object']).columns:
        mobile_df[col] = mobile_df[col].str.lower()
    
    # Remove duplicates
    mobile_df = mobile_df.drop_duplicates()

    # Drop unnecessary columns price_inr and specs
    mobile_df = mobile_df.drop(columns=['price_inr', 'specs'], errors='ignore')

    # Making a price column in numeric format by removing commas
    mobile_df['price'] = mobile_df['price'].astype(str).str.replace('[₹,]', '', regex=True)
    mobile_df['price'] = pd.to_numeric(mobile_df['price'], errors='coerce')
    
    # Remove rows where price could not be converted (are NaN)
    mobile_df.dropna(subset=['price'], inplace=True)

    # Remove the outlier rows using the IQR method for the 'price' column
    Q1 = mobile_df['price'].quantile(0.25)
    Q3 = mobile_df['price'].quantile(0.75)
    IQR = Q3 - Q1
    lower_bound = Q1 - 1.5 * IQR
    upper_bound = Q3 + 1.5 * IQR
    mobile_df = mobile_df[(mobile_df['price'] >= lower_bound) & (mobile_df['price'] <= upper_bound)]

    # converting all object columns as category data types
    for col in mobile_df.select_dtypes(include='object').columns:
        mobile_df[col] = mobile_df[col].astype('category')
        
    return mobile_df

def convert_unknowns_to_nan(data_frame: pd.DataFrame) -> pd.DataFrame:
    """
    This function finds all cells with the exact string 'unknown'
    and replaces them with a proper np.nan (Not a Number) value.
    """
    # .replace() is the correct and safe method.
    df_cleaned = data_frame.replace('unknown', np.nan)
    return df_cleaned

def impute_missing_numerical_data(data_frame: pd.DataFrame) -> pd.DataFrame:
    """
    Uses KNNImputer to fill missing values in specified numerical columns.
    """
    imputer = KNNImputer(n_neighbors=5)
    
    numerical_cols = [
       'processor_speed_ghz', 'ram_gb', 'storage_gb',
       'fast_charging_w', 'display_width', 'total_pixels', 'display_ppi',
       'refresh_rate_hz', 'front_camera_mp', 'total_camera_mp',
       'price_per_gb_ram', 'price_per_gb_storage'
    ]
    
    # Check which columns actually exist in the DataFrame before attempting imputation
    cols_to_impute = [col for col in numerical_cols if col in data_frame.columns]

    if cols_to_impute:
        data_frame[cols_to_impute] = imputer.fit_transform(data_frame[cols_to_impute])
    
    return data_frame

def process_processor_column(data_frame: pd.DataFrame) -> pd.DataFrame:
    """
    Cleans, normalizes, and maps processor names.
    """
    # Ensure it's treated as string initially for cleaning operations
    data_frame['processor'] = data_frame['processor'].astype(str)

    data_frame['processor'] = (
        data_frame['processor']
        .str.lower()
        .str.strip()
        .str.replace(r'\s+', ' ', regex=True)
    )

    # Safely restore NaN before mappings
    data_frame['processor'] = data_frame['processor'].replace({'nan': np.nan})
    
    # Apply mapping
    mapping = {
        'snapdragon 8+ gen1': 'snapdragon 8 plus gen1',
        'snapdragon  8 gen1': 'snapdragon 8 gen1',
        'snapdragon 778g+': 'snapdragon 778g plus',
        'helio  p22': 'helio p22',
        'dimensity  900': 'dimensity 900'
    }
    data_frame['processor'] = data_frame['processor'].replace(mapping)
    
    # Convert to category last
    data_frame['processor'] = data_frame['processor'].astype('category')
    
    return data_frame

def load_to_mysql(df: pd.DataFrame, db_name: str, table_name: str, user: str = 'root', password: str = 'root', host: str = 'localhost'):
    """
    Creates a MySQL database and writes the DataFrame to a specified table.
    """
    # --- Step 1: Create a server-level engine ---
    server_engine_url = f"mysql+mysqlconnector://{user}:{password}@{host}"
    server_engine = create_engine(server_engine_url, pool_recycle=3600)

    # --- Step 2: Create the database using a connection ---
    try:
        with server_engine.connect() as conn:
            # Use a raw connection to execute DDL statements like CREATE DATABASE
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {db_name}"))
            conn.commit() # Commit the DDL operation
        print(f"Database '{db_name}' created or already exists.")
    except Exception as e:
        print(f"Error creating database: {e}")
        return

    # --- Step 3: Create a NEW engine that connects *directly* to that database ---
    db_engine_url = f"mysql+mysqlconnector://{user}:{password}@{host}/{db_name}"
    db_engine = create_engine(db_engine_url, pool_recycle=3600)

    # --- Step 4: Write the DataFrame using the new, database-specific engine ---
    try:
        # If your DataFrame contains categorical data, ensure pandas handles mapping to appropriate types for SQL
        df.to_sql(table_name, con=db_engine, if_exists='replace', index=False)
        print(f"DataFrame successfully written to '{db_name}.{table_name}'")
    except Exception as e:
        print(f"An error occurred during to_sql operation: {e}")


# --- Main Execution Flow ---

if __name__ == '__main__':
    # Define file paths
    cleaned_csv_path = 'mobile_cleaned.csv'
    eda_csv_path = 'mobile_eda.csv'
    
    # --- Data Preprocessing ---
    mobile_df = load_and_preprocess_mobile_data(cleaned_csv_path)
    print(f"Shape after preprocessing: {mobile_df.shape}")
    
    mobile_df = convert_unknowns_to_nan(mobile_df)
    
    mobile_df = impute_missing_numerical_data(mobile_df)
    mobile_df.info()

    # Filter out 'flip' phones
    if pd.api.types.is_categorical_dtype(mobile_df['name']):
        mobile_df['name'] = mobile_df['name'].astype(str)
    mobile_df = mobile_df[~mobile_df['name'].str.contains('flip', na=False)]

    mobile_df = process_processor_column(mobile_df)
    print(f"Unique processors count: {len(mobile_df['processor'].unique().tolist())}")

    df_eda = pd.read_csv(eda_csv_path)

    load_to_mysql(
        df=df_eda,
        db_name=os.getenv('DB_NAME'),
        table_name='mobile_eda', 
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        host=os.getenv('DB_HOST')
    )
