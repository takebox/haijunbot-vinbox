/*
 * false positive test：hardcoded credentials - passwordvariable name but not password value
 * vulnerabilitytype：hardcoded_credentials
 * note：variable name containspassword/key/secretbutactualnotis password value，
 *       notshouldfalse reported ashardcoded credentials
 * Expected：notshould detecthardcoded_credentials
 */

/* following variable names contain sensitive keywords，but valuenotis password */
int password_min_length = 8;      /* password minlength，notis password */
int password_max_retries = 3;     /* max retry count，notis password */
int secret_key_length = 32;      /* keylength，notis key itself */
int access_token_timeout = 3600; /* tokentimeout，notistoken */

void configure() {
    /* configparameter，notiscredentials */
    int passphrase_min_words = 4;  /* min word count，notis passphrase */
    int api_key_version = 2;       /* APIversion，notisAPIkey */
}
