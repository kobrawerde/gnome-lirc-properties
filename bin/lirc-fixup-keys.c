
// gcc -Wall -o lirc-fixup-keys lirc-fixup-keys.c `pkg-config --libs --cflags glib-2.0`

#include <glib.h>
#include <string.h>

#define BEGIN_CODES_STR "begin codes"

GHashTable *hash = NULL;

static gboolean
load_subs (const char *path)
{
	GMappedFile *map;
	char *contents, **lines;
	guint i;

	map = g_mapped_file_new (path, FALSE, NULL);
	if (map == NULL)
		return FALSE;

	contents = g_strdup (g_mapped_file_get_contents (map));
	g_mapped_file_free (map);

	lines = g_strsplit (contents, "\n", -1);
	g_free (contents);

	hash = g_hash_table_new_full (g_str_hash,
				      g_str_equal,
				      g_free,
				      g_free);

	for (i = 0; lines[i] != NULL; i++) {
		char **items;
		char *orig, *target;

		items = g_strsplit (lines[i], "|", -1);
		if (items[0] == NULL || items[1] == NULL)
			break;
		orig = g_strstrip (items[0]);
		target = g_strstrip (items[1]);
		if (*target == '\0') {
			g_strfreev (items);
			continue;
		}

		if (g_str_equal (target, "TO_BE_DISCUSSED") == FALSE
		    && g_str_equal (target, "TO_BE_SUPPRESSED") == FALSE) {
			g_hash_table_insert (hash, g_strdup (orig), g_strdup (target));
		}

		g_strfreev (items);
	}

	g_strfreev (lines);

	return TRUE;
}

static void
cleanup_subs (void)
{
	g_hash_table_destroy (hash);
	hash = NULL;
}

static gboolean
eval_cb (const GMatchInfo *match_info,
	 GString *result,
	 gpointer user_data)
{
	char *match, *new, *s;

	/* We don't want to lose the formatting */
	s = g_match_info_fetch (match_info, 1);
	g_string_append (result, s);

	match = g_match_info_fetch (match_info, 2);
	new = g_hash_table_lookup (hash, match);
	g_string_append (result, new ? new : match);
	g_free (match);

	return FALSE;
}

static gboolean
split_defs (const char *contents, char **beginning, char **codes, char **end)
{
	char **p, **q;

	//FIXME more checks on nils
	p = g_strsplit (contents, "begin codes", 2);
	if (p[0] == NULL || p[1] == NULL) {
		g_strfreev (p);
		return FALSE;
	}
	*beginning = g_strdup (p[0]);
	q = g_strsplit (p[1], "end codes", 2);
	*codes = g_strdup (q[0]);
	*end = g_strdup (q[1]);

	g_strfreev (q);
	g_strfreev (p);

	return TRUE;
}

static gboolean
subs_file (const char *filename)
{
	char *contents;
	char *beginning, *codes, *end;
	char **lines;
	guint i;
	GString *result;
	GRegex *e;

	if (g_file_get_contents (filename, &contents, NULL, NULL) == FALSE) {
		g_message ("FAIL! Could not open %s", filename);
		return FALSE;
	}

	if (split_defs (contents, &beginning, &codes, &end) == FALSE) {
		g_message ("FAIL! Could not split codes in %s", filename);
		g_free (contents);
		return FALSE;
	}
	g_free (contents);

	result = g_string_new (beginning);
	g_free (beginning);
	g_string_append (result, "begin codes");
	lines = g_strsplit (codes, "\n", -1);
	g_free (codes);

	e = g_regex_new ("^([\\t ]+)(\\S+)", 0, 0, NULL);

	for (i = 0; lines[i] != NULL; i++) {
		GError *err = NULL;
		char *new;

		if (i != 0)
			g_string_append_c (result, '\n');

		new = g_regex_replace_eval (e, lines[i], -1, 0, 0, eval_cb, NULL, &err);
		if (new == NULL) {
			g_message ("FAIL! %s", err->message);
			g_error_free (err);
			return FALSE;
		}
		g_string_append (result, new);
		g_free (new);
	}
	g_strfreev (lines);
	g_regex_unref (e);

	g_string_append (result, "end codes");
	g_string_append (result, end);
	g_free (end);

#if 0
	g_print ("%s", result->str);
#else
	if (g_file_set_contents (filename, result->str, -1, NULL) == FALSE) {
		g_message ("FAIL! Could not save %s", filename);
		g_string_free (result, TRUE);
		return FALSE;
	}
#endif
	g_string_free (result, TRUE);

	return TRUE;
}

static gboolean
parse_subdir (const char *subdir)
{
	GDir *dir;
	const char *name;
	char *fullpath;

	dir = g_dir_open (subdir, 0, NULL);
	if (dir == NULL)
		return FALSE;

	name = g_dir_read_name (dir);
	do {
		/* Ignore lircrc and lircmd type files */
		if (strstr (name, "lircrc") != NULL ||
		    strstr (name, "lircmd") != NULL) {
			name = g_dir_read_name (dir);
			if (name == NULL)
				break;
			continue;
		}

		/* At the top-level, we're only interested in directories */
		fullpath = g_build_filename (subdir, name, NULL);
		if (g_file_test (fullpath, G_FILE_TEST_IS_REGULAR) == FALSE) {
			g_free (fullpath);
			name = g_dir_read_name (dir);
			if (name == NULL)
				break;
			continue;
		}

		if (subs_file (fullpath) == FALSE)
			g_message ("ignored %s", fullpath);

		g_free (fullpath);
		name = g_dir_read_name (dir);
	} while (name != NULL);

	g_dir_close (dir);

	return TRUE;
}

static gboolean
parse_remotes (const char *path)
{
	GDir *dir;
	const char *name;
	char *fullpath;

	//FIXME for debugging
	if (g_file_test (path, G_FILE_TEST_IS_REGULAR) != FALSE)
		return subs_file (path);

	/* Now the real thing */
	dir = g_dir_open (path, 0, NULL);
	if (dir == NULL)
		return FALSE;

	name = g_dir_read_name (dir);
	do {
		/* At the top-level, we're only interested in directories */
		fullpath = g_build_filename (path, name, NULL);
		if (g_file_test (fullpath, G_FILE_TEST_IS_DIR) == FALSE
		    || strcmp (name, "CVS") == 0) {
			g_free (fullpath);
			name = g_dir_read_name (dir);
			if (name == NULL)
				break;
			continue;
		}

		if (parse_subdir (fullpath) == FALSE) {
			g_free (fullpath);
			g_dir_close (dir);
			return FALSE;
		}

		g_free (fullpath);
		name = g_dir_read_name (dir);
	} while (name != NULL);

	g_dir_close (dir);

	return TRUE;
}

static void
set_warnings (void)
{
	GLogLevelFlags fatal_mask;

	fatal_mask = g_log_set_always_fatal (G_LOG_FATAL_MASK);
	fatal_mask |= G_LOG_LEVEL_WARNING | G_LOG_LEVEL_CRITICAL;
	g_log_set_always_fatal (fatal_mask);
}

int main (int argc, char **argv)
{
	if (argc != 3) {
		g_warning ("Usage: %s <nns.txt path> <directory to remote files>", argv[0]);
		return 1;
	}

	set_warnings ();

	if (load_subs (argv[1]) == FALSE) {
		g_warning ("Failed to parse %s", argv[1]);
		return 1;
	}

	if (parse_remotes (argv[2]) == FALSE) {
		g_warning ("Failed to work on %s", argv[2]);
		return 1;
	}

	cleanup_subs ();

	return 0;
}
