"""
Gradio Web Application for Google Analytics 4 and Search Console Data
"""
import gradio as gr
import pandas as pd
import os
from datetime import datetime, timedelta
import io
import tempfile

# Import our API modules
import GA4query3
import search_console_api


def get_ga4_data(start_date, end_date, property_id, auth_identifier, dimensions, metrics, filter_expr, debug):
    """
    Fetch GA4 data using GA4query3 module
    """
    try:
        # Convert property_id to string if provided, otherwise use None for all properties
        prop_id = str(property_id).strip() if property_id and str(property_id).strip() else None
        
        if prop_id:
            # Single property
            df = GA4query3.produce_report(
                start_date=start_date,
                end_date=end_date,
                property_id=prop_id,
                property_name="WebUI_Property",
                account=auth_identifier,
                filter_expression=filter_expr if filter_expr.strip() else None,
                dimensions=dimensions,
                metrics=metrics,
                debug=debug
            )
        else:
            # All properties - list them first, then get data for each
            properties_df = GA4query3.list_properties(auth_identifier, debug=debug)
            if properties_df is None or properties_df.empty:
                return None, "No properties found or authentication failed"
            
            combined_df = pd.DataFrame()
            for _, row in properties_df.iterrows():
                prop_id = str(row['property_id'])
                prop_name = str(row['property_name'])
                
                df_property = GA4query3.produce_report(
                    start_date=start_date,
                    end_date=end_date,
                    property_id=prop_id,
                    property_name=prop_name,
                    account=auth_identifier,
                    filter_expression=filter_expr if filter_expr.strip() else None,
                    dimensions=dimensions,
                    metrics=metrics,
                    debug=debug
                )
                
                if df_property is not None:
                    df_property['property_id'] = prop_id
                    df_property['property_name'] = prop_name
                    combined_df = pd.concat([combined_df, df_property], ignore_index=True)
            
            df = combined_df if not combined_df.empty else None
        
        if df is not None and not df.empty:
            return df, f"Successfully retrieved {len(df)} rows of GA4 data"
        else:
            return None, "No data returned or authentication failed"
            
    except Exception as e:
        return None, f"Error fetching GA4 data: {str(e)}"


def get_gsc_data(start_date, end_date, google_account, search_type, dimensions, wait_seconds, debug):
    """
    Fetch Google Search Console data using search_console_api module
    """
    try:
        df = search_console_api.fetch_search_console_data(
            start_date=start_date,
            end_date=end_date,
            search_type=search_type,
            dimensions=dimensions,
            google_account=google_account,
            wait_seconds=wait_seconds,
            debug=debug
        )
        
        if df is not None and not df.empty:
            return df, f"Successfully retrieved {len(df)} rows of Search Console data"
        else:
            return None, "No data returned or authentication failed"
            
    except Exception as e:
        return None, f"Error fetching Search Console data: {str(e)}"


def query_data(data_source, start_date, end_date, ga4_property_id, ga4_auth_id, ga4_dimensions, 
               ga4_metrics, ga4_filter, gsc_account, gsc_search_type, gsc_dimensions, 
               gsc_wait_seconds, debug_mode):
    """
    Main function to query data based on selected source
    """
    if not start_date or not end_date:
        return None, "Please provide both start and end dates"
    
    if data_source == "Google Analytics 4 (GA4)":
        if not ga4_auth_id.strip():
            return None, "Please provide GA4 Auth Identifier"
        
        df, message = get_ga4_data(
            start_date, end_date, ga4_property_id, ga4_auth_id.strip(), 
            ga4_dimensions, ga4_metrics, ga4_filter, debug_mode
        )
    else:  # Google Search Console
        df, message = get_gsc_data(
            start_date, end_date, gsc_account, gsc_search_type, 
            gsc_dimensions, gsc_wait_seconds, debug_mode
        )
    
    return df, message


def download_csv(df):
    """
    Generate CSV download link for the dataframe
    """
    if df is None or df.empty:
        return None
    
    # Create a temporary file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"data_export_{timestamp}.csv"
    
    # Save to temp directory
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    df.to_csv(temp_path, index=False)
    
    return temp_path


def list_ga4_properties(auth_identifier):
    """
    List available GA4 properties for the authenticated user
    """
    if not auth_identifier.strip():
        return None, "Please provide GA4 Auth Identifier"
    
    try:
        properties_df = GA4query3.list_properties(auth_identifier.strip(), debug=False)
        if properties_df is not None and not properties_df.empty:
            return properties_df, f"Found {len(properties_df)} GA4 properties"
        else:
            return None, "No properties found or authentication failed"
    except Exception as e:
        return None, f"Error listing properties: {str(e)}"


# Create the Gradio interface
with gr.Blocks(title="Google Analytics & Search Console Data Fetcher", theme=gr.themes.Soft()) as app:
    gr.Markdown("# Google Analytics 4 & Search Console Data Fetcher")
    gr.Markdown("Fetch data from Google Analytics 4 or Google Search Console with a web interface.")
    
    with gr.Row():
        with gr.Column(scale=1):
            # Data source selection
            data_source = gr.Radio(
                choices=["Google Analytics 4 (GA4)", "Google Search Console (GSC)"],
                value="Google Analytics 4 (GA4)",
                label="Data Source"
            )
            
            # Common fields
            start_date = gr.Textbox(
                label="Start Date",
                placeholder="yyyy-mm-dd (e.g., 2024-01-01)",
                value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
            )
            
            end_date = gr.Textbox(
                label="End Date", 
                placeholder="yyyy-mm-dd (e.g., 2024-01-31)",
                value=datetime.now().strftime("%Y-%m-%d")
            )
            
            debug_mode = gr.Checkbox(label="Debug Mode", value=False)
            
            # GA4 specific fields
            with gr.Group(visible=True) as ga4_group:
                gr.Markdown("### GA4 Settings")
                ga4_auth_id = gr.Textbox(
                    label="Auth Identifier",
                    placeholder="e.g., myproject (for token file naming)",
                    info="Base name for OAuth token files"
                )
                ga4_property_id = gr.Textbox(
                    label="Property ID (optional)",
                    placeholder="Leave empty for all properties or enter specific property ID",
                    info="Leave empty to fetch data from all accessible properties"
                )
                ga4_dimensions = gr.Textbox(
                    label="Dimensions",
                    value="pagePath",
                    placeholder="e.g., pagePath or hostname,pagePath"
                )
                ga4_metrics = gr.Textbox(
                    label="Metrics",
                    value="screenPageViews",
                    placeholder="e.g., screenPageViews,totalAdRevenue"
                )
                ga4_filter = gr.Textbox(
                    label="Filter (optional)",
                    placeholder="e.g., pagePath=your_page_path"
                )
                
                list_properties_btn = gr.Button("List Available GA4 Properties")
            
            # GSC specific fields  
            with gr.Group(visible=False) as gsc_group:
                gr.Markdown("### Search Console Settings")
                gsc_account = gr.Textbox(
                    label="Google Account",
                    placeholder="Account identifier for secrets/tokens",
                    info="Used for client secrets file naming"
                )
                gsc_search_type = gr.Radio(
                    choices=["web", "image", "video"],
                    value="web",
                    label="Search Type"
                )
                gsc_dimensions = gr.Textbox(
                    label="Dimensions",
                    value="page",
                    placeholder="e.g., page, query, page,query"
                )
                gsc_wait_seconds = gr.Number(
                    label="Wait Seconds",
                    value=0,
                    minimum=0,
                    info="Delay between API calls to prevent quota issues"
                )
            
            # Query button
            query_btn = gr.Button("Fetch Data", variant="primary", size="lg")
        
        with gr.Column(scale=2):
            # Results section
            status_text = gr.Textbox(label="Status", interactive=False, lines=2)
            
            # Data display
            data_table = gr.Dataframe(
                label="Results",
                interactive=False,
                wrap=True
            )
            
            # Download button
            download_btn = gr.File(label="Download CSV", visible=False)
            
            # Properties list for GA4
            properties_table = gr.Dataframe(
                label="Available GA4 Properties",
                visible=False,
                interactive=False
            )
    
    # Event handlers
    def toggle_fields(source):
        """Toggle visibility of fields based on data source"""
        if source == "Google Analytics 4 (GA4)":
            return gr.update(visible=True), gr.update(visible=False)
        else:
            return gr.update(visible=False), gr.update(visible=True)
    
    def process_query(*args):
        """Process the data query and update interface"""
        df, message = query_data(*args)
        
        if df is not None and not df.empty:
            # Generate download file
            csv_file = download_csv(df)
            return (
                message,
                df,
                gr.update(value=csv_file, visible=True),
                gr.update(visible=False)  # Hide properties table
            )
        else:
            return (
                message,
                None,
                gr.update(visible=False),
                gr.update(visible=False)
            )
    
    def show_properties(auth_id):
        """Show available GA4 properties"""
        df, message = list_ga4_properties(auth_id)
        if df is not None:
            return message, gr.update(value=df, visible=True)
        else:
            return message, gr.update(visible=False)
    
    # Wire up the event handlers
    data_source.change(
        fn=toggle_fields,
        inputs=[data_source],
        outputs=[ga4_group, gsc_group]
    )
    
    query_btn.click(
        fn=process_query,
        inputs=[
            data_source, start_date, end_date, ga4_property_id, ga4_auth_id, 
            ga4_dimensions, ga4_metrics, ga4_filter, gsc_account, gsc_search_type, 
            gsc_dimensions, gsc_wait_seconds, debug_mode
        ],
        outputs=[status_text, data_table, download_btn, properties_table]
    )
    
    list_properties_btn.click(
        fn=show_properties,
        inputs=[ga4_auth_id],
        outputs=[status_text, properties_table]
    )


# For REST API functionality
def api_query_data(source, start_date, end_date, **kwargs):
    """
    REST API endpoint for querying data
    """
    if source.lower() == "ga4":
        df, message = get_ga4_data(
            start_date=start_date,
            end_date=end_date,
            property_id=kwargs.get('property_id'),
            auth_identifier=kwargs.get('auth_identifier', ''),
            dimensions=kwargs.get('dimensions', 'pagePath'),
            metrics=kwargs.get('metrics', 'screenPageViews'),
            filter_expr=kwargs.get('filter', ''),
            debug=kwargs.get('debug', False)
        )
    else:  # gsc
        df, message = get_gsc_data(
            start_date=start_date,
            end_date=end_date,
            google_account=kwargs.get('google_account', ''),
            search_type=kwargs.get('search_type', 'web'),
            dimensions=kwargs.get('dimensions', 'page'),
            wait_seconds=kwargs.get('wait_seconds', 0),
            debug=kwargs.get('debug', False)
        )
    
    if df is not None:
        return {
            "status": "success",
            "message": message,
            "data": df.to_dict('records'),
            "row_count": len(df)
        }
    else:
        return {
            "status": "error", 
            "message": message,
            "data": [],
            "row_count": 0
        }


def api_list_ga4_properties(auth_identifier):
    """
    REST API endpoint for listing GA4 properties
    """
    df, message = list_ga4_properties(auth_identifier)
    if df is not None:
        return {
            "status": "success",
            "message": message,
            "properties": df.to_dict('records')
        }
    else:
        return {
            "status": "error",
            "message": message,
            "properties": []
        }


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Google Analytics & Search Console Data Fetcher")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=7860, help="Port to bind to")
    parser.add_argument("--share", action="store_true", help="Create a public shareable link")
    parser.add_argument("--auth", help="Set authentication for the interface (username:password)")
    
    args = parser.parse_args()
    
    # Configure authentication if provided
    auth_config = None
    if args.auth:
        try:
            username, password = args.auth.split(":", 1)
            auth_config = (username, password)
        except ValueError:
            print("Invalid auth format. Use username:password")
            exit(1)
    
    print("Starting Google Analytics & Search Console Data Fetcher...")
    print(f"Server will run on http://{args.host}:{args.port}")
    if args.share:
        print("A public shareable link will be created.")
    
    # Launch the app
    app.launch(
        server_name=args.host,
        server_port=args.port,
        share=args.share,
        auth=auth_config,
        show_api=True  # Enable REST API documentation
    )